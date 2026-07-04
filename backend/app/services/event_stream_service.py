from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any

import anyio
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.models.agent_run import AgentRun
from backend.app.models.run_event import RunEvent
from backend.app.repositories.agent_runs import AgentRunRepository
from backend.app.repositories.run_events import RunEventRepository


TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled"}


class EventStreamService:
    def __init__(
        self,
        *,
        poll_interval_seconds: float = 0.5,
        heartbeat_interval_seconds: float = 15.0,
    ) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    async def stream_run_events(
        self,
        *,
        db_session_factory: Callable[[], Session] = SessionLocal,
        user_id: str,
        run_id: str,
        after_sequence_no: int | None = None,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        last_sequence_no = after_sequence_no or 0
        seconds_since_heartbeat = 0.0

        while True:
            if is_disconnected is not None and await is_disconnected():
                return

            events, run = await anyio.to_thread.run_sync(
                self._load_events,
                db_session_factory,
                user_id,
                run_id,
                last_sequence_no,
            )
            if run is None:
                return

            for event in events:
                last_sequence_no = event.sequence_no
                yield self.format_event(event, run_id)

            if run.status in TERMINAL_RUN_STATUSES:
                return

            if seconds_since_heartbeat >= self.heartbeat_interval_seconds:
                seconds_since_heartbeat = 0.0
                yield self.format_heartbeat()

            await anyio.sleep(self.poll_interval_seconds)
            seconds_since_heartbeat += self.poll_interval_seconds

    def _load_events(
        self,
        db_session_factory: Callable[[], Session],
        user_id: str,
        run_id: str,
        after_sequence_no: int,
    ) -> tuple[list[RunEvent], AgentRun | None]:
        db = db_session_factory()
        try:
            run = AgentRunRepository(db).get_for_user(run_id, user_id)
            if run is None:
                return [], None
            events = RunEventRepository(db).list_for_run(
                user_id=user_id,
                run_id=run_id,
                after_sequence_no=after_sequence_no,
                limit=200,
            )
            return events, run
        finally:
            db.close()

    def format_event(self, event: RunEvent, run_id: str) -> str:
        payload = {
            "run_id": run_id,
            "sequence_no": event.sequence_no,
            "event_type": event.event_type,
            "event_json": event.event_json,
            "created_at": self._serialize_datetime(event.created_at),
        }
        return (
            f"id: {event.sequence_no}\n"
            f"event: {event.event_type}\n"
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        )

    def format_heartbeat(self) -> str:
        payload = {"event_type": "heartbeat"}
        return f"event: heartbeat\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

