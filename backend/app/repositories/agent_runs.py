from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.agent_run import AgentRun
from backend.app.models.base import utc_now


class AgentRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(
        self,
        user_id: str,
        conversation_id: str,
        input_message_id: str | None,
        status: str = "queued",
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            input_message_id=input_message_id,
            status=status,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def mark_running(self, run_id: str, user_id: str) -> AgentRun | None:
        run = self.get_for_user(run_id, user_id)
        if run is None:
            return None
        run.status = "running"
        run.started_at = utc_now()
        self.db.flush()
        return run

    def mark_succeeded(self, run_id: str, user_id: str) -> AgentRun | None:
        run = self.get_for_user(run_id, user_id)
        if run is None:
            return None
        run.status = "succeeded"
        run.finished_at = utc_now()
        self.db.flush()
        return run

    def mark_failed(self, run_id: str, user_id: str, error_message: str) -> AgentRun | None:
        run = self.get_for_user(run_id, user_id)
        if run is None:
            return None
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = utc_now()
        self.db.flush()
        return run

    def get_for_user(self, run_id: str, user_id: str) -> AgentRun | None:
        return self.db.scalar(
            select(AgentRun).where(
                AgentRun.id == run_id,
                AgentRun.user_id == user_id,
            )
        )

