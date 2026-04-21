"""One-time script to create the Job Application Tracking database in Notion.

PREREQUISITE:
  1. Open Notion in your browser
  2. Create any page (or use an existing one)
  3. Click '...' menu → 'Connections' → Add your integration
  4. Run this script with: python scripts/setup_notion_db.py <PAGE_URL_OR_ID>

The script will create the tracking database inside that page.
"""
from __future__ import annotations

import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NOTION_API_KEY")
BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def notion_request(method: str, path: str, body: dict | None = None) -> dict:
    resp = requests.request(method, f"{BASE_URL}{path}", headers=HEADERS, json=body, timeout=30)
    if not resp.ok:
        print(f"Notion API error ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def extract_page_id(input_str: str) -> str:
    """Extract a Notion page ID from a URL or raw ID string."""
    # Match the 32-char hex ID at the end of a Notion URL
    match = re.search(r"([a-f0-9]{32})", input_str.replace("-", ""))
    if match:
        raw = match.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return input_str


def create_database(parent_page_id: str) -> str:
    """Create the application tracking database with the required schema."""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "Job Application Tracker"}}],
        "properties": {
            "Application": {"title": {}},
            "Company": {"rich_text": {}},
            "Source": {
                "select": {
                    "options": [
                        {"name": "linkedin", "color": "blue"},
                        {"name": "naukri", "color": "orange"},
                    ]
                }
            },
            "Pipeline Status": {
                "select": {
                    "options": [
                        {"name": "scraped", "color": "gray"},
                        {"name": "matched", "color": "yellow"},
                        {"name": "resume_generated", "color": "blue"},
                        {"name": "applied", "color": "green"},
                        {"name": "manual_review_required", "color": "red"},
                        {"name": "rejected", "color": "brown"},
                    ]
                }
            },
            "Match Score": {"number": {"format": "percent"}},
            "Location": {"rich_text": {}},
            "Job URL": {"url": {}},
            "Search Query": {"rich_text": {}},
            "Matched Skills": {"rich_text": {}},
            "Notes": {"rich_text": {}},
            "Applied At": {"date": {}},
        },
    }
    result = notion_request("POST", "/databases", body)
    return result["id"]


def main():
    if not API_KEY:
        print("Error: NOTION_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_notion_db.py <NOTION_PAGE_URL_OR_ID>")
        print()
        print("Steps:")
        print("  1. Open Notion and create a page (e.g. 'Job Automation AI')")
        print("  2. Click '...' → 'Connections' → Add your integration")
        print("  3. Copy the page URL from your browser")
        print("  4. Run: .venv/bin/python3 scripts/setup_notion_db.py <PASTE_URL_HERE>")
        sys.exit(1)

    page_id = extract_page_id(sys.argv[1])
    print(f"Using parent page: {page_id}")

    print("Creating database: 'Job Application Tracker'...")
    db_id = create_database(page_id)
    print(f"  Database created: {db_id}")

    print(f"\n{'='*60}")
    print(f"SUCCESS! Update your config.yaml with:")
    print(f"  application_tracking_data_source_id: {db_id}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
