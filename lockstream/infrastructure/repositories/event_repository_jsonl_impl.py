from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from lockstream.core.entities.event import Event
from lockstream.core.repositories.event_repository import EventRepository
from lockstream.infrastructure.models.models import EventStore


class JsonlEventRepositoryImpl(EventRepository):
    """
    Event repository backed by an append-only JSONL EventStore.

    Responsibilities:
      - translate between core Event entities and persisted dict records
      - expose repository API (add_if_absent/get/iter_events)

    Persistence details (append/existence check/streaming reads) are delegated to EventStore.
    """

    def __init__(self, *, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._store = EventStore(path)
        self._event_field_names: set[str] = {f.name for f in fields(Event)}

    def add_if_absent(self, event: Event) -> bool:
        record = self._event_to_record(event)
        return self._store.append(record)


    @staticmethod
    def _event_to_record(event: Event) -> dict[str, Any]:
        """
        Normalize datetimes and events for persistence
        """
        record = asdict(event)
        record["event_id"] = str(event.event_id)
        record["occurred_at"] = event.occurred_at.isoformat()
        record["type"] = event.type.value

        return record