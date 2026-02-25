from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from lockstream.core.entities.event import Event
from lockstream.core.use_cases.ingest_event import IngestEventUseCase


class EventLogReader(Protocol):
    """
    Read-only access to the append-only event log (JSONL).
    Your JSONL repository can implement this via iter_events().
    """

    def iter_events(self) -> Sequence[Event]:
        raise NotImplementedError


class ProjectionResetter(Protocol):
    """
    Clears the in-memory projection (SQLite) to rebuild from scratch
    """

    def reset(self) -> None:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class RebuildProjectionResult:
    replayed_events: int


class RebuildLockerProjectionUseCase:
    """
    Rebuild the in-memory DB projection from the append-only event log.
    """

    def __init__(
        self,
        *,
        event_log: EventLogReader,
        projector: IngestEventUseCase,
        resetter: ProjectionResetter,
    ) -> None:
        self._event_log = event_log
        self._projector = projector
        self._resetter = resetter

    def execute(self) -> RebuildProjectionResult:
        self._resetter.reset()

        replayed = 0
        for event in self._event_log.iter_events():
            self._projector.project(event)
            replayed += 1

        return RebuildProjectionResult(replayed_events=replayed)