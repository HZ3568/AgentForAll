from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_active_user
from backend.app.models.user import User
from backend.app.runtime.session_manager import AgentRunConflict
from backend.app.schemas.agent import AgentTurnRequest, AgentTurnResponse
from backend.app.services.agent_service import (
    AgentConversationNotFound,
    AgentService,
    AgentTurnExecutionError,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent_service(db: Annotated[Session, Depends(get_db)]) -> AgentService:
    return AgentService(db)


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

