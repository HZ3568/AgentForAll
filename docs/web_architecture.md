# Web Architecture

AgentForAll 的正式 Web 层采用三层架构，依赖方向固定为：

```text
frontend -> backend -> codeagent
```

## frontend

React + Vite + TypeScript 用户交互层。

- 负责对话工作台、任务看板、学习计划日历、Memory 管理和工具调用日志视图。
- 只能通过 `backend` HTTP/SSE/WebSocket API 与系统交互。
- 不能直接 import 或调用 `codeagent`。

## backend

FastAPI Web 服务层。

- 负责 HTTP API、用户认证、权限校验、MySQL 持久化、会话隔离和运行状态管理。
- 可以 import `codeagent`，但必须通过 adapter/service 层调用 Runtime。
- 路由层不直接承载 Agent 核心逻辑。
- 所有 conversation、message、tool、task、memory 查询都必须校验当前用户所有权。

## codeagent

Agent 核心能力层。

- 负责 Runtime、Agent Loop、工具池、Memory、Tasks、MCP、CLI 等能力。
- 不依赖 `backend` 或 `frontend`。
- 不引入 FastAPI、SQLAlchemy、JWT、MySQL、React 等 Web 层概念。
- CLI 继续使用本地 `.sessions/.memory/.tasks` 文件机制；Web 端后续以 MySQL 作为主要持久化。

## Phase 0 Scope

- 删除旧原型 Web。
- 建立 FastAPI 最小服务骨架。
- 暴露 `GET /api/v1/health`。
- 保留 CLI 和 `codeagent/core` Agent Loop。
- 暂不实现用户系统、数据库模型、React 页面和 Agent 对话接口。

## Phase 1 Database Scope

- `backend` 使用 MySQL + SQLAlchemy + Alembic 管理 Web 数据库。
- 所有 Web 用户私有数据表必须包含 `user_id`。
- Repository 查询 conversation、message、tool、task、memory 时必须显式传入 `user_id` 并校验所有权。
- Repository 层只处理数据库，不处理 HTTP，也不调用 Agent Runtime。
- 详细说明见 [backend_database.md](backend_database.md)。
