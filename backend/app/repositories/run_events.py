from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.run_event import RunEvent


class RunEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event(
        self,
        user_id: str,
        conversation_id: str,
        run_id: str,
        event_type: str,
        event_json: dict[str, Any] | list[Any] | None,
        sequence_no: int,
    ) -> RunEvent:
        event = RunEvent(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            event_type=event_type,
            event_json=event_json if event_json is not None else {},
            sequence_no=sequence_no,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_for_run(self, user_id: str, run_id: str) -> list[RunEvent]:
        stmt = (
            select(RunEvent)
            .where(RunEvent.user_id == user_id, RunEvent.run_id == run_id)
            .order_by(RunEvent.sequence_no.asc())
        )
        return list(self.db.scalars(stmt))

