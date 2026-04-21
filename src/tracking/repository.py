from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import ApplicationRecord


class TrackingRepository(ABC):
    @abstractmethod
    def upsert(self, record: ApplicationRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_records(self) -> list[ApplicationRecord]:
        raise NotImplementedError

