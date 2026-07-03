# Backend Database

The backend database layer is owned by `backend`. It uses MySQL in production, SQLAlchemy 2.x typed ORM models, and Alembic migrations.

## Ownership Boundary

- `backend` owns Web users, conversations, messages, run events, tool logs, Web memory, Web tasks, schedules, and uploaded file metadata.
- `codeagent` does not know about MySQL, SQLAlchemy, Alembic, JWT, or HTTP.
- Repository code does not call the Agent Runtime.
- A later adapter layer will translate backend conversation rows into `codeagent` history messages when the Agent API is introduced.

## Core Tables

- `users` stores authentication-ready user records.
- `conversations` groups Web chat sessions by `user_id`.
- `messages` stores ordered conversation messages with `sequence_no`.
- `agent_runs`, `run_events`, `tool_calls`, and `tool_results` store execution state and audit trails.
- `memories` stores Web-layer memory records; it does not reuse `.memory/MEMORY.md`.
- `tasks` and `scheduled_jobs` store Web-layer planning state.
- `workspace_files` stores metadata for files managed by the backend.

## User Isolation

All user-private tables include `user_id`. Repository methods for conversations and messages must receive `user_id` and filter by it explicitly.

Required patterns:

- `ConversationRepository.get_for_user(conversation_id, user_id)`
- `MessageRepository.list_for_conversation(user_id, conversation_id)`
- `MessageRepository.create_message(...)` must verify the conversation belongs to `user_id` before writing.

Do not add repository methods that read private data by `conversation_id` alone.

## Migrations

Run Alembic from the repository root:

```bash
alembic -c backend/alembic.ini upgrade head
```

For local migration checks without MySQL, override `DATABASE_URL`:

```bash
DATABASE_URL=sqlite:///./backend_alembic_check.db alembic -c backend/alembic.ini upgrade head
```

Production table creation must use Alembic. `Base.metadata.create_all()` is allowed only inside tests for temporary databases.
