from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

from src.models import ApplicationRecord
from src.utils.config import NotionSyncConfig
from src.utils.retry import retry_sync


class NotionAPIClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        notion_version: str,
        timeout_sec: int,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": notion_version,
                "Content-Type": "application/json",
            }
        )

    @retry_sync(attempts=3)
    def query_database(
        self,
        *,
        database_id: str,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict:
        payload: dict[str, object] = {
            "page_size": min(page_size, 100),
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor
        return self._request(
            "POST",
            f"/databases/{database_id}/query",
            json_body=payload,
        )

    @retry_sync(attempts=3)
    def create_page(self, *, database_id: str, properties: dict) -> dict:
        return self._request(
            "POST",
            "/pages",
            json_body={
                "parent": {"database_id": database_id},
                "properties": properties,
            },
        )

    @retry_sync(attempts=3)
    def update_page(self, *, page_id: str, properties: dict) -> dict:
        return self._request(
            "PATCH",
            f"/pages/{page_id}",
            json_body={"properties": properties},
        )

    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=json_body,
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        return response.json()


@dataclass
class NotionSyncSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0


class NotionApplicationTrackingSync:
    def __init__(
        self,
        config: NotionSyncConfig,
        logger: logging.Logger,
        api_client: NotionAPIClient | None = None,
    ) -> None:
        self.config = config
        self.logger = logger.getChild("notion_sync")
        self._api_client = api_client

    def is_enabled(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.application_tracking_data_source_id
            and os.getenv(self.config.api_key_env_var)
        )

    def sync_records(self, records: list[ApplicationRecord]) -> NotionSyncSummary:
        if not self.config.enabled:
            self.logger.info("Notion sync disabled in config.")
            return NotionSyncSummary(skipped=len(records))

        api_key = os.getenv(self.config.api_key_env_var)
        if not api_key:
            self.logger.warning(
                "Notion sync enabled but %s is not set. Skipping sync.",
                self.config.api_key_env_var,
            )
            return NotionSyncSummary(skipped=len(records))

        if not self.config.application_tracking_data_source_id:
            self.logger.warning("Notion sync enabled but data source ID is missing. Skipping sync.")
            return NotionSyncSummary(skipped=len(records))

        if not records:
            return NotionSyncSummary()

        api_client = self._get_api_client(api_key)
        existing_pages = self._load_existing_pages_by_job_url(api_client)
        summary = NotionSyncSummary()

        for record in records[: self.config.max_records_per_sync]:
            properties = self.build_notion_properties(record)
            page_id = existing_pages.get(record.job_url)
            if page_id:
                api_client.update_page(page_id=page_id, properties=properties)
                summary.updated += 1
            else:
                response = api_client.create_page(
                    database_id=self.config.application_tracking_data_source_id,
                    properties=properties,
                )
                existing_pages[record.job_url] = response["id"]
                summary.created += 1

        skipped_records = max(len(records) - self.config.max_records_per_sync, 0)
        summary.skipped += skipped_records
        self.logger.info(
            "Notion sync complete. created=%s updated=%s skipped=%s",
            summary.created,
            summary.updated,
            summary.skipped,
        )
        return summary

    def build_notion_properties(self, record: ApplicationRecord) -> dict[str, dict]:
        properties: dict[str, dict] = {
            "Application": self._title_property(record.job_title),
            "Company": self._rich_text_property(record.company),
            "Source": {"select": {"name": record.source}},
            "Pipeline Status": {"select": {"name": self._normalize_status(record.status)}},
            "Match Score": {"number": round(record.match_score, 4)},
            "Location": self._rich_text_property(record.location),
            "Job URL": {"url": record.job_url},
            "Search Query": self._rich_text_property(record.search_query),
            "Matched Skills": self._rich_text_property(", ".join(record.matched_skills)),
            "Notes": self._rich_text_property(record.notes),
        }
        properties["Applied At"] = {
            "date": {"start": record.applied_at.isoformat()} if record.applied_at else None
        }
        return properties

    def _load_existing_pages_by_job_url(self, api_client: NotionAPIClient) -> dict[str, str]:
        existing_pages: dict[str, str] = {}
        next_cursor: str | None = None

        while True:
            response = api_client.query_database(
                database_id=self.config.application_tracking_data_source_id,
                start_cursor=next_cursor,
                page_size=100,
            )
            for result in response.get("results", []):
                job_url = self._extract_url_property(result.get("properties", {}), "Job URL")
                if job_url:
                    existing_pages[job_url] = result["id"]

            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
            if not next_cursor:
                break

        return existing_pages

    def _get_api_client(self, api_key: str) -> NotionAPIClient:
        if self._api_client is None:
            self._api_client = NotionAPIClient(
                api_key=api_key,
                base_url=self.config.api_base_url,
                notion_version=self.config.notion_version,
                timeout_sec=self.config.request_timeout_sec,
            )
        return self._api_client

    @staticmethod
    def _extract_url_property(properties: dict, name: str) -> str:
        value = properties.get(name) or {}
        return value.get("url") or ""

    @staticmethod
    def _normalize_status(status: str) -> str:
        if status == "manual_action_required":
            return "manual_review_required"
        return status

    @staticmethod
    def _title_property(value: str) -> dict[str, list[dict]]:
        return {
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": NotionApplicationTrackingSync._truncate(value),
                    },
                }
            ]
            if value
            else []
        }

    @staticmethod
    def _rich_text_property(value: str) -> dict[str, list[dict]]:
        if not value:
            return {"rich_text": []}
        return {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": NotionApplicationTrackingSync._truncate(value),
                    },
                }
            ]
        }

    @staticmethod
    def _truncate(value: str, limit: int = 2000) -> str:
        return (value or "")[:limit]
