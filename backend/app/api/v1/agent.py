from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, get_db
from backend.app.core.deps import require_active_user
from backend.app.models.user import User
from backend.app.repositories.agent_runs import AgentRunRepository
from backend.app.repositories.run_events import RunEventRepository
from backend.app.runtime.session_manager import AgentRunConflict
from backend.app.schemas.agent import (
    AgentRunCancelResponse,
    AgentRunCreateRequest,
    AgentRunCreateResponse,
    AgentRunEventsResponse,
    AgentRunRead,
    AgentTurnRequest,
    AgentTurnResponse,
)
from backend.app.services.agent_service import (
    AgentConversationNotFound,
    AgentRunNotFound,
    AgentService,
    AgentTurnExecutionError,
)
from backend.app.services.event_stream_service import EventStreamService
from backend.app.services.run_worker_service import RunWorkerService

router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent_service(db: Annotated[Session, Depends(get_db)]) -> AgentService:
    return AgentService(db)


def get_run_worker_service() -> RunWorkerService:
    return RunWorkerService()


def get_event_stream_service() -> EventStreamService:
    return EventStreamService()


def get_db_session_factory() -> Callable[[], Session]:
    return SessionLocal


@router.post(
    "/conversations/{conversation_id}/turn",
    response_model=AgentTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_agent_turn(
    conversation_id: str,
    payload: AgentTurnRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentTurnResponse:
    try:
        result = service.run_turn(
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except AgentConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    except AgentRunConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation already has a running agent turn.",
        ) from exc
    except AgentTurnExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent run failed: {exc}",
        ) from exc

    return AgentTurnResponse(
        run_id=result.run.id,
        status=result.run.status,
        conversation_id=conversation_id,
        user_message=result.user_message,
        assistant_messages=result.assistant_messages,
        events=result.events,
        tool_calls=result.tool_calls,
        error=result.run.error_message,
    )


@router.post(
    "/conversations/{conversation_id}/runs",
    response_model=AgentRunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_agent_run(
    conversation_id: str,
    payload: AgentRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    worker: Annotated[RunWorkerService, Depends(get_run_worker_service)],
) -> AgentRunCreateResponse:
    try:
        created = service.create_run(
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except AgentConversationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    except AgentRunConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation already has a running agent turn.",
        ) from exc

    background_tasks.add_task(worker.execute_run, current_user.id, created.run.id)
    return AgentRunCreateResponse(
        run_id=created.run.id,
        conversation_id=created.run.conversation_id,
        status=created.run.status,
        user_message=created.user_message,
        events_url=created.events_url,
    )


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_agent_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    run = AgentRunRepository(db).get_for_user(run_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


@router.get("/runs/{run_id}/events", response_model=AgentRunEventsResponse)
def list_agent_run_events(
    run_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    after_sequence_no: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> AgentRunEventsResponse:
    if AgentRunRepository(db).get_for_user(run_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    events = RunEventRepository(db).list_for_run(
        user_id=current_user.id,
        run_id=run_id,
        after_sequence_no=after_sequence_no,
        limit=limit,
    )
    return AgentRunEventsResponse(run_id=run_id, events=events)


@router.get("/runs/{run_id}/events/stream")
def stream_agent_run_events(
    run_id: str,
    request: Request,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    stream_service: Annotated[EventStreamService, Depends(get_event_stream_service)],
    db_session_factory: Annotated[Callable[[], Session], Depends(get_db_session_factory)],
    after_sequence_no: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    if AgentRunRepository(db).get_for_user(run_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    return StreamingResponse(
        stream_service.stream_run_events(
            db_session_factory=db_session_factory,
            user_id=current_user.id,
            run_id=run_id,
            after_sequence_no=after_sequence_no,
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentRunCancelResponse)
def cancel_agent_run(
    run_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentRunCancelResponse:
    try:
        run = service.cancel_run(user_id=current_user.id, run_id=run_id)
    except AgentRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.") from exc
    return AgentRunCancelResponse(run_id=run.id, status=run.status)
