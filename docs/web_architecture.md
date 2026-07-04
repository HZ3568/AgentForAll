# Web Architecture

AgentForAll 的正式 Web 层采用三层架构，依赖方向固定为：

```text
frontend -> backend -> codeagent
```

## frontend

React + Vite + TypeScript 用户交互层。

- 只通过 `backend` API 与系统通信。
- 不直接 import 或调用 `codeagent`。
- 阶段 4 使用 fetch + ReadableStream 订阅 SSE，携带 Authorization header。
- 不把 JWT 放进 URL query。

## backend

FastAPI Web 服务层。

- 负责 HTTP API、JWT 鉴权、权限校验、MySQL 持久化、会话隔离和运行状态管理。
- 通过 service/runtime adapter 调用 `codeagent`。
- API router 不直接 import `codeagent`。
- Repository 查询用户私有数据时必须显式绑定 `user_id`。
- MySQL 是 run state 和 run events 的权威数据源；SSE 只是实时传输通道。

## codeagent

Agent 核心能力层。

- 负责 Runtime、Agent Loop、工具池、Memory、Tasks、MCP、CLI。
- 不依赖 `backend` 或 `frontend`。
- 不引入 FastAPI、SQLAlchemy、JWT、MySQL、SSE、React 等 Web 层概念。
- CLI 继续使用本地 `.sessions/.memory/.tasks` 文件机制。

## 阶段进展

- 阶段 0：移除旧 Streamlit Web，建立 FastAPI 最小骨架。
- 阶段 1：建立 MySQL、SQLAlchemy、Alembic、ORM 和 Repository 地基。
- 阶段 2：实现 Auth、Conversation、Message API 和最小 React 前端。
- 阶段 3：接入非流式 Agent turn，持久化 run、event、tool call、tool result 和 assistant message。
- 阶段 4：新增异步 run、SSE run events、run 状态查询、cancel run 和前端实时 Agent 工作台。

## Runtime 边界

`backend/app/runtime/agent_adapter.py` 负责把数据库消息转换为 codeagent history，调用 `agent_loop`，再把新增消息、工具调用和事件转换回 backend 内部类型。

`backend/app/services/agent_service.py` 负责数据库事务、用户隔离和 run 生命周期。

`backend/app/services/event_stream_service.py` 只读取 `run_events` 并输出 SSE，不调用 Agent Runtime。

## Workspace 隔离

```text
.runtime_workspaces/
  user_<user_id>/
    .memory/
    conv_<conversation_id>/
      scratch/
      uploads/
      artifacts/
      traces/
      codeagent_web_config.yaml
```

Web Runtime 的 scope 分工：

- `user_<user_id>/.memory/` 是用户级长期记忆，同一用户的多个 conversation 共享。
- `conv_<conversation_id>/` 是会话级文件工作区，工具读写、scratch、uploads、artifacts、traces 都限制在这里。
- `.tasks/.mailboxes/.worktrees` 仍保持 conversation 级，并按需创建，避免跨会话串扰。

Adapter 写入 `codeagent_web_config.yaml` 时同时设置 `workdir` 和 `memory_dir`。CLI 默认不设置 `memory_dir`，继续使用本地 `<workdir>/.memory`。

旧 conversation 级 memory 可通过非破坏性脚本合并：

```bash
python scripts/migrate_runtime_memory.py --dry-run
python scripts/migrate_runtime_memory.py --apply
```

当前目录隔离用于 Web 运行态组织。工具层更细粒度的文件访问限制会在后续阶段增强。
