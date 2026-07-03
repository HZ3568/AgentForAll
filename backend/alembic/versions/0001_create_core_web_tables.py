"""create core web tables

Revision ID: 0001_create_core_web_tables
Revises:
Create Date: 2026-07-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_core_web_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_conversations_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index("ix_conversations_user_last_message_at", "conversations", ["user_id", "last_message_at"])
    op.create_index("ix_conversations_user_updated_at", "conversations", ["user_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_messages_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_messages_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_conversation_sequence_no", "messages", ["conversation_id", "sequence_no"])
    op.create_index("ix_messages_user_created_at", "messages", ["user_id", "created_at"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("input_message_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_agent_runs_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["input_message_id"], ["messages.id"], name=op.f("fk_agent_runs_input_message_id_messages")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_agent_runs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index("ix_agent_runs_conversation_created_at", "agent_runs", ["conversation_id", "created_at"])
    op.create_index("ix_agent_runs_user_status", "agent_runs", ["user_id", "status"])

    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_memories_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memories_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memories")),
    )
    op.create_index("ix_memories_conversation_id", "memories", ["conversation_id"])
    op.create_index("ix_memories_user_scope", "memories", ["user_id", "scope"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("cron_expr", sa.String(length=128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_scheduled_jobs_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_scheduled_jobs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_jobs")),
    )
    op.create_index("ix_scheduled_jobs_user_enabled", "scheduled_jobs", ["user_id", "enabled"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_tasks_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_tasks_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index("ix_tasks_conversation_id", "tasks", ["conversation_id"])
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])

    op.create_table(
        "workspace_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_workspace_files_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_workspace_files_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_files")),
    )
    op.create_index("ix_workspace_files_user_conversation", "workspace_files", ["user_id", "conversation_id"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_json", sa.JSON(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_run_events_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_run_events_run_id_agent_runs")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_run_events_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_events")),
    )
    op.create_index("ix_run_events_conversation_created_at", "run_events", ["conversation_id", "created_at"])
    op.create_index("ix_run_events_run_sequence_no", "run_events", ["run_id", "sequence_no"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_input_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_tool_calls_conversation_id_conversations")),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_tool_calls_run_id_agent_runs")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_tool_calls_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
    )
    op.create_index("ix_tool_calls_run_created_at", "tool_calls", ["run_id", "created_at"])
    op.create_index("ix_tool_calls_user_tool_name", "tool_calls", ["user_id", "tool_name"])

    op.create_table(
        "tool_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tool_call_id", sa.String(length=36), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tool_call_id"], ["tool_calls.id"], name=op.f("fk_tool_results_tool_call_id_tool_calls")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_results")),
        sa.UniqueConstraint("tool_call_id", name=op.f("uq_tool_results_tool_call_id")),
    )


def downgrade() -> None:
    op.drop_table("tool_results")
    op.drop_index("ix_tool_calls_user_tool_name", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_created_at", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_run_events_run_sequence_no", table_name="run_events")
    op.drop_index("ix_run_events_conversation_created_at", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_workspace_files_user_conversation", table_name="workspace_files")
    op.drop_table("workspace_files")
    op.drop_index("ix_tasks_user_status", table_name="tasks")
    op.drop_index("ix_tasks_conversation_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_scheduled_jobs_user_enabled", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
    op.drop_index("ix_memories_user_scope", table_name="memories")
    op.drop_index("ix_memories_conversation_id", table_name="memories")
    op.drop_table("memories")
    op.drop_index("ix_agent_runs_user_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_conversation_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_messages_user_created_at", table_name="messages")
    op.drop_index("ix_messages_conversation_sequence_no", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_user_last_message_at", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("users")
