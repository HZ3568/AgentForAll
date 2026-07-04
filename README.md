# AgentForAll

面向多业务场景的通用 Agent Runtime。

AgentForAll 将 Agent 主循环、工具调用、权限控制、Hook、Memory、任务调度和评估体系封装为可复用的核心能力层。正式 Web 架构采用 **React + FastAPI + MySQL**，并保持依赖方向单向：`frontend -> backend -> codeagent`。

## 架构边界

- `frontend`：React + Vite + TypeScript 用户交互层，只通过 backend API 通信。
- `backend`：FastAPI 服务层，负责 HTTP API、认证授权、MySQL 持久化、用户隔离和 Runtime 适配。
- `codeagent`：Agent 核心能力层，负责 Runtime、Agent Loop、工具池、Memory、Tasks、MCP 和 CLI。

`codeagent` 不依赖 Web 层，不引入 FastAPI、SQLAlchemy、JWT、MySQL 或 React 概念；CLI 继续直接使用 `codeagent` 自身能力。

## 技术栈

| Layer | Stack |
|---|---|
| Frontend | React, Vite, TypeScript |
| Backend | FastAPI, SQLAlchemy, Alembic, PyMySQL, JWT |
| Agent Core | Python, Anthropic Messages API, Tool Calling |
| Memory & Trace | Markdown, JSON, JSONL |
| Evaluation | GAIA Benchmark, pytest |

## 阶段 0

当前阶段完成 Web 架构清理和最小后端骨架：

- 删除旧原型 Web。
- 新增 `backend` FastAPI 服务。
- 新增 `/api/v1/health` 健康检查。
- 预留 `frontend` 工作区。
- 保留 `codeagent` CLI、本地 `.sessions/.memory/.tasks` 文件机制和 Agent Loop 核心逻辑。

## 阶段 1

当前阶段补齐 backend 数据库地基：

- 使用 SQLAlchemy 2.x typed ORM 定义 Web 层核心表。
- 使用 Alembic 管理 MySQL 迁移。
- 建立 Repository 层，conversation/message 查询必须显式传入 `user_id`。
- 新增用户隔离测试，确保用户 A 不能读取或写入用户 B 的会话消息。
- 阶段 1 不调用 `codeagent` Runtime，不实现 Agent 对话接口。

## 阶段 2

当前阶段实现最小 Web 产品闭环：

- 注册、登录、`/auth/me` 和 JWT Bearer 鉴权。
- Conversation / Message API，所有查询绑定 `current_user.id`。
- React + Vite + TypeScript 前端骨架，支持注册、登录、创建会话、查看消息和发送用户消息。
- 阶段 2 不接入 Agent Runtime，不生成 assistant 回复，不实现 SSE/WebSocket。

## 架构图

```mermaid
flowchart LR
    Frontend[frontend React UI] --> Backend[backend FastAPI API]
    Backend --> Adapter[Runtime Adapter / Service]
    Adapter --> Core[codeagent Runtime]
    Core --> LLM[LLM API]
    Core --> Tools[Tool Registry]
    Core --> Memory[Memory / Tasks / MCP]
    Backend --> DB[(MySQL)]
```

## 快速开始

```bash
cd AgentForAll
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

创建 `.env`：

```env
ANTHROPIC_API_KEY=your_key_here
MODEL_ID=claude-sonnet-4-20250514

DATABASE_URL=mysql+pymysql://agentforall:agentforall@localhost:3306/agentforall
JWT_SECRET_KEY=change-me-in-development
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

BRAVE_SEARCH_API_KEY=
TAVILY_API_KEY=
```

运行 CLI：

```bash
python -m codeagent
```

运行 FastAPI：

```bash
uvicorn backend.app.main:app --reload
```

运行前端：

```bash
cd frontend
npm install
npm run dev
```

运行数据库迁移：

```bash
alembic -c backend/alembic.ini upgrade head
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

运行测试：

```bash
pytest -q
```

## GAIA 评估

项目已接入 GAIA Benchmark，支持样本过滤、严格证据模式、工具轨迹记录和官方 JSONL 格式导出。

实验记录中，GAIA Level 1：

- Exact Match：**53.20%**
- Partial Match：**34.57%**

```bash
python -m codeagent.evaluation.gaia.run_eval --level 1 --max-samples 5 --gaia-eval-mode strict
```

## 目录结构

```text
AgentForAll
├── backend/         # FastAPI Web 服务层
├── frontend/        # React 前端工作区
├── codeagent/       # Agent 核心能力层与 CLI
├── docs/
├── skills/
└── tests/
```

更多 Web 架构边界见 [docs/web_architecture.md](docs/web_architecture.md)。
数据库设计见 [docs/backend_database.md](docs/backend_database.md)。
API 说明见 [docs/backend_api.md](docs/backend_api.md)。
