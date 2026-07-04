from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
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

    def get_next_sequence_no(self, run_id: str, user_id: str) -> int:
        current_max = self.db.scalar(
            select(func.max(RunEvent.sequence_no)).where(
                RunEvent.user_id == user_id,
                RunEvent.run_id == run_id,
            )
        )
        return int(current_max or 0) + 1

    def get_latest_sequence_no(self, user_id: str, run_id: str) -> int:
        current_max = self.db.scalar(
            select(func.max(RunEvent.sequence_no)).where(
                RunEvent.user_id == user_id,
                RunEvent.run_id == run_id,
            )
        )
        return int(current_max or 0)

    def list_for_run(
        self,
        user_id: str,
        run_id: str,
        after_sequence_no: int | None = None,
        limit: int = 200,
    ) -> list[RunEvent]:
        stmt = (
            select(RunEvent)
            .where(RunEvent.user_id == user_id, RunEvent.run_id == run_id)
            .order_by(RunEvent.sequence_no.asc())
            .limit(limit)
        )
        if after_sequence_no is not None:
            stmt = stmt.where(RunEvent.sequence_no > after_sequence_no)
        return list(self.db.scalars(stmt))
