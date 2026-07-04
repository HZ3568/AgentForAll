# Backend API

Phase 2 exposes the minimum Web API for user-owned conversations and user messages. These APIs are implemented in `backend` and do not call `codeagent`.

## Authentication

Use JWT access tokens:

```http
Authorization: Bearer <token>
```

Implemented endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

`register` stores only `password_hash`; password values are never returned.

## Conversations

Implemented endpoints:

- `GET /api/v1/conversations`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `PATCH /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`

All conversation operations bind to `current_user.id`. Other users' conversations return `404`.

## Messages

Implemented endpoints:

- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages`

Phase 2 only stores `role=user` messages. `POST` persists:

```json
{
  "content_json": {"type": "text", "text": "..."},
  "content_text": "..."
}
```

No assistant response is generated in this phase.

## User Isolation

- Conversation and message routes depend on the authenticated user.
- Repository queries must include `user_id`.
- The API returns `404` for another user's conversation or messages to avoid leaking object existence.

## Phase 2 Limits

- No Agent Runtime integration.
- No assistant replies.
- No SSE or WebSocket.
- No tool-call timeline.
- No memory sync.

## Phase 3 Plan

- Add `AgentSessionManager`.
- Add a non-streaming Agent turn API.
- Persist assistant replies into `messages`.
- Persist run state into `agent_runs`, `run_events`, `tool_calls`, and `tool_results`.
