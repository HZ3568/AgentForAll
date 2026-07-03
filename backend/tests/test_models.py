from __future__ import annotations

from backend.app.models import Base


def test_core_web_tables_are_registered():
    expected_tables = {
        "users",
        "conversations",
        "messages",
        "agent_runs",
        "run_events",
        "tool_calls",
        "tool_results",
        "memories",
        "tasks",
        "scheduled_jobs",
        "workspace_files",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_user_private_tables_have_user_id():
    user_scoped_tables = {
        "conversations",
        "messages",
        "agent_runs",
        "run_events",
        "tool_calls",
        "memories",
        "tasks",
        "scheduled_jobs",
        "workspace_files",
    }

    for table_name in user_scoped_tables:
        assert "user_id" in Base.metadata.tables[table_name].columns
