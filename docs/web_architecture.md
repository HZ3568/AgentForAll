# Web Architecture

AgentForAll 的正式 Web 层采用三层架构，依赖方向固定为：

```text
frontend -> backend -> codeagent
```

## frontend

React + Vite + TypeScript 用户交互层。

- 只通过 `backend` API 与系统通信。
- 不直接 import 或调用 `codeagent`。
- 阶段 3 调用非流式 Agent turn API，展示用户消息、assistant 回复、运行状态和工具调用摘要。

## backend

FastAPI Web 服务层。

- 负责 HTTP API、JWT 鉴权、权限校验、MySQL 持久化、会话隔离和运行状态管理。
- 通过 service/runtime adapter 调用 `codeagent`。
- API router 不直接 import `codeagent`。
- Repository 查询用户私有数据时必须显式绑定 `user_id`。

## codeagent

Agent 核心能力层。

- 负责 Runtime、Agent Loop、工具池、Memory、Tasks、MCP、CLI。
- 不依赖 `backend` 或 `frontend`。
- 不引入 FastAPI、SQLAlchemy、JWT、MySQL、React 等 Web 层概念。
- CLI 继续使用本地 `.sessions/.memory/.tasks` 文件机制。

## 阶段进展

- 阶段 0：移除旧 Streamlit Web，建立 FastAPI 最小骨架。
- 阶段 1：建立 MySQL、SQLAlchemy、Alembic、ORM 和 Repository 地基。
- 阶段 2：实现 Auth、Conversation、Message API 和最小 React 前端。
- 阶段 3：通过 `AgentRuntimeAdapter` 接入非流式 Agent turn，持久化 run、event、tool call、tool result 和 assistant message。

## Runtime Adapter 边界

`backend/app/runtime/agent_adapter.py` 是 backend 中唯一直接 import `codeagent` 的位置。它负责把数据库消息转换为 codeagent history，调用 `agent_loop`，再把新增消息、工具调用和事件转换回 backend 内部类型。

`backend/app/services/agent_service.py` 负责数据库事务和权限边界。它不重写 Agent Loop，也不把 MySQL 写入 `codeagent`。

## Workspace 隔离

阶段 3 为每个用户会话创建独立目录：

```text
.runtime_workspaces/
  user_<user_id>/
    conv_<conversation_id>/
      scratch/
      uploads/
      artifacts/
      traces/
```

当前目录隔离用于 Web 运行态组织。工具层更细粒度的文件访问限制会在后续阶段增强。
