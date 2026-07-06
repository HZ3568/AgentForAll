from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.agent_run import AgentRun
from backend.app.models.base import utc_now


ACTIVE_RUN_STATUSES = {"queued", "running", "cancelling"}


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

    def mark_cancelling(self, run_id: str, user_id: str) -> AgentRun | None:
        run = self.get_for_user(run_id, user_id)
        if run is None:
            return None
        if run.status in {"succeeded", "failed", "cancelled"}:
            return run
        run.status = "cancelling"
        self.db.flush()
        return run

    def mark_cancelled(self, run_id: str, user_id: str) -> AgentRun | None:
        run = self.get_for_user(run_id, user_id)
        if run is None:
            return None
        run.status = "cancelled"
        run.finished_at = utc_now()
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

    def list_active_for_conversation(self, user_id: str, conversation_id: str) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.user_id == user_id,
                AgentRun.conversation_id == conversation_id,
                AgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
            .order_by(AgentRun.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def list_for_conversation(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 10,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.user_id == user_id,
                AgentRun.conversation_id == conversation_id,
            )
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
