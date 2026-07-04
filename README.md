# AgentForAll

面向多业务场景的通用 Agent Runtime。

AgentForAll 将 Agent 主循环、工具调用、权限 Hook、Memory、任务调度和评估能力封装为可复用核心层，并通过 **React + FastAPI + MySQL** 提供正式 Web 架构。系统边界保持单向依赖：

```text
frontend -> backend -> codeagent
```

## 架构

- `frontend`：React + Vite + TypeScript 交互层，只调用 backend API。
- `backend`：FastAPI 服务层，负责认证、权限校验、MySQL 持久化、会话隔离、SSE 事件流和 Runtime 适配。
- `codeagent`：Agent 核心能力层，负责 Runtime、Agent Loop、工具池、Memory、Tasks、MCP 和 CLI。

`codeagent` 不依赖 Web 层，不引入 FastAPI、SQLAlchemy、JWT、MySQL、SSE 或 React。CLI 继续直接使用 `codeagent` 自身能力。

## 技术栈

| Layer | Stack |
|---|---|
| Frontend | React, Vite, TypeScript |
| Backend | FastAPI, SQLAlchemy, Alembic, PyMySQL, JWT, SSE |
| Agent Core | Python, Anthropic Messages API, Tool Calling |
| Memory & Trace | Markdown, JSON, JSONL |
| Evaluation | GAIA Benchmark, pytest |

## 当前阶段

- 阶段 0：移除旧 Streamlit Web，建立 FastAPI 最小骨架。
- 阶段 1：建立 MySQL、SQLAlchemy、Alembic、ORM 和 Repository 层。
- 阶段 2：实现注册、登录、Conversation / Message API 和最小 React 前端。
- 阶段 3：接入非流式 Agent turn API，持久化 assistant message、agent run、run event、tool call 和 tool result。
- 阶段 4：新增异步 run、SSE run events、run 状态查询、cancel run 和前端实时 Agent 工作台。

阶段 4 暂不实现 WebSocket、复杂工具审批、文件上传、Memory 同步和多进程分布式队列。

## Runtime Scope

Web Runtime 将 conversation 文件工作区和 user 长期记忆分开：

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

- `workdir` 指向 `conv_<conversation_id>/`，工具读写仍按会话隔离。
- `memory_dir` 指向 `user_<user_id>/.memory/`，同一用户的多个会话共享长期记忆。
- CLI 默认不设置 `memory_dir`，继续使用 `<workdir>/.memory`。

旧 conversation 级 memory 可非破坏性合并：

```bash
python scripts/migrate_runtime_memory.py --dry-run
python scripts/migrate_runtime_memory.py --apply
```

## 目录

```text
AgentForAll/
├── backend/      # FastAPI Web 服务层
├── frontend/     # React 用户交互层
├── codeagent/    # Agent 核心能力层与 CLI
├── docs/         # 架构、API、数据库和 Runtime Adapter 文档
└── tests/        # codeagent 侧测试
```

## 快速开始

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

创建 `.env`：

```env
ANTHROPIC_API_KEY=your_key_here
MODEL_ID=claude-sonnet-4-20250514

DATABASE_URL=mysql+pymysql://agentforall:agentforall@localhost:3306/agentforall
JWT_SECRET_KEY=change-me-in-development
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
WORKSPACE_ROOT=.runtime_workspaces

BRAVE_SEARCH_API_KEY=
TAVILY_API_KEY=
```

执行数据库迁移：

```bash
alembic -c backend/alembic.ini upgrade head
```

启动后端：

```bash
python scripts/dev_backend.py
```

开发脚本只监听 `backend/` 和 `codeagent/` 的源码变化，不监听 `.runtime_workspaces/`。如果直接使用 uvicorn，请至少限制 reload 目录：

```bash
uvicorn backend.app.main:app --reload --reload-dir backend --reload-dir codeagent
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

运行 CLI：

```bash
python -m codeagent
```

运行测试：

```bash
pytest -q
```

构建前端：

```bash
cd frontend
npm run build
```

## Web API

核心入口：

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/conversations`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/turn`
- `POST /api/v1/agent/conversations/{conversation_id}/runs`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/runs/{run_id}/events`
- `GET /api/v1/agent/runs/{run_id}/events/stream`
- `POST /api/v1/agent/runs/{run_id}/cancel`

`/turn` 保留同步非流式能力。`/runs` 是阶段 4 的实时工作台入口：它快速返回 `run_id`，后台执行 Agent，前端通过 SSE 订阅 `run_events`。

## GAIA 评估

项目已接入 GAIA Benchmark，支持样本过滤、严格证据模式、工具轨迹记录和官方 JSONL 格式导出。

实验记录中，GAIA Level 1：

- Exact Match：**53.20%**
- Partial Match：**34.57%**

```bash
python -m codeagent.evaluation.gaia.run_eval --level 1 --max-samples 5 --gaia-eval-mode strict
```

## 文档

- [Web 架构](docs/web_architecture.md)
- [Backend API](docs/backend_api.md)
- [Backend Database](docs/backend_database.md)
- [Agent Runtime Adapter](docs/agent_runtime_adapter.md)
- [Streaming Events](docs/streaming_events.md)
