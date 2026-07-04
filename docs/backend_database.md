# Backend Database

`backend` 拥有 Web 数据库层。生产目标数据库是 MySQL，ORM 使用 SQLAlchemy 2.x，迁移使用 Alembic。`codeagent` 不知道 MySQL、SQLAlchemy、Alembic、JWT、SSE 或 HTTP。

## 核心表

- `users`：Web 用户、角色和状态。
- `conversations`：按 `user_id` 隔离的会话。
- `messages`：会话内有序消息，使用 `sequence_no` 保持顺序。
- `agent_runs`：一次 Agent turn/run 的运行状态。
- `run_events`：运行生命周期和关键事件，是 SSE 的权威事件来源。
- `tool_calls`：Agent 运行中的工具调用摘要。
- `tool_results`：工具调用结果，通过 `tool_call_id` 关联。
- `memories`：Web 层 memory 记录，不直接复用 CLI 的 `.memory/MEMORY.md`。
- `tasks`、`scheduled_jobs`：Web 层任务和计划。
- `workspace_files`：后续文件上传和工作区文件元数据。

## 关系

```text
users 1 -> n conversations
conversations 1 -> n messages
conversations 1 -> n agent_runs
agent_runs 1 -> n run_events
agent_runs 1 -> n tool_calls
tool_calls 1 -> 1 tool_results
```

`messages.input_for_runs` 通过 `agent_runs.input_message_id` 关联一次运行的用户输入。

## 用户隔离

所有用户私有表都必须能绑定 `user_id`。Repository 必须使用以下模式：

- `ConversationRepository.get_for_user(conversation_id, user_id)`
- `MessageRepository.list_for_conversation(user_id, conversation_id)`
- `AgentRunRepository.get_for_user(run_id, user_id)`
- `RunEventRepository.list_for_run(user_id, run_id, ...)`
- `ToolCallRepository.list_for_run(user_id, run_id)`
- `ToolResultRepository` 通过 `tool_calls.user_id` 校验所有权。

不要新增只按 `conversation_id` 或 `run_id` 读取用户私有数据的方法。

## Agent Run 持久化

异步 run 的写入顺序：

1. 校验 conversation 属于当前用户。
2. 写入 `role=user` message。
3. 创建 `agent_runs`，初始状态为 `queued`。
4. 写入 `run_queued` 和 `user_message_created`。
5. 后台 worker 标记 run 为 `running`，写入 `run_started`。
6. 调用 runtime adapter。
7. 写入 `assistant_delta`、tool events、assistant message 和 `assistant_message_created`。
8. 成功时写入 `run_finished` 并标记 `succeeded`。
9. 失败时写入 `run_failed` 并标记 `failed`。
10. 取消时写入 `run_cancel_requested`，最终写入 `run_cancelled`。

Agent 失败不会回滚已经创建的 user message 和 failed run。

## Alembic

从仓库根目录运行：

```bash
alembic -c backend/alembic.ini upgrade head
```

本地没有 MySQL 时可以临时覆盖：

```bash
DATABASE_URL=sqlite:///./backend_alembic_check.db alembic -c backend/alembic.ini upgrade head
```

生产建表必须使用 Alembic。`Base.metadata.create_all()` 只允许在测试临时数据库中使用。
