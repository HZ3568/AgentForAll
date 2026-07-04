from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.repositories.agent_runs import AgentRunRepository
from backend.app.repositories.run_events import RunEventRepository
from backend.app.runtime.session_manager import (
    AgentSessionManager,
    get_default_agent_session_manager,
)
from backend.app.services.agent_service import AgentService, AgentTurnExecutionError


class RunWorkerService:
    def __init__(
        self,
        db_session_factory: Callable[[], Session] = SessionLocal,
        session_manager: AgentSessionManager | None = None,
    ) -> None:
        self.db_session_factory = db_session_factory
        self.session_manager = session_manager or get_default_agent_session_manager()

    def execute_run(self, user_id: str, run_id: str) -> None:
        db = self.db_session_factory()
        try:
            AgentService(db, session_manager=self.session_manager).execute_run(
                user_id=user_id,
                run_id=run_id,
            )
        except AgentTurnExecutionError:
            return
        except Exception as exc:
            self._mark_unhandled_failure(db, user_id, run_id, exc)
        finally:
            db.close()

    def _mark_unhandled_failure(self, db: Session, user_id: str, run_id: str, exc: Exception) -> None:
        run_repo = AgentRunRepository(db)
        run = run_repo.get_for_user(run_id, user_id)
        if run is None:
            return
        public_error = f"{type(exc).__name__}: {exc}"[:1000]
        event_repo = RunEventRepository(db)
        event_repo.create_event(
            user_id=user_id,
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type="run_failed",
            event_json={"message": public_error},
            sequence_no=event_repo.get_next_sequence_no(run.id, user_id),
        )
        run_repo.mark_failed(run.id, user_id, public_error)
        db.commit()

