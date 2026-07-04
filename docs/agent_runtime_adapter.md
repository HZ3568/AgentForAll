# Agent Runtime Adapter

`AgentRuntimeAdapter` 是 backend 与 `codeagent` Runtime 的边界。它允许 Web 层复用 `codeagent` 的 Agent Loop，同时不把 HTTP、SSE、数据库、JWT 或用户隔离逻辑写进 `codeagent`。

## 边界

- `codeagent` 不 import `backend`。
- `codeagent` 不知道 FastAPI、MySQL、SQLAlchemy、JWT、SSE 或 React。
- API router 不直接调用 `codeagent`。
- backend 中只有 runtime/service 边界可以触达 Agent 执行能力。
- `backend/app/runtime/agent_adapter.py` 是直接 import `codeagent` 的位置。

## Adapter 职责

`codeagent.core.loop.agent_loop(runtime, messages, context)` 会原地修改 `messages`。Adapter 负责：

1. 将 MySQL messages 转换为 codeagent history。
2. 创建 codeagent runtime。
3. 调用 `agent_loop`。
4. 对比调用前后的 history，提取新增 assistant message。
5. 提取 tool_use 和 tool_result。
6. 返回 backend 内部 `AgentTurnResult`。

Adapter 不直接操作数据库，不接收 FastAPI Request/Response，不做权限判断。

## Service 生命周期

阶段 4 中 `AgentService` 拆分为：

- `create_run()`：校验用户、写 user message、创建 queued run、写 `run_queued` 和 `user_message_created`。
- `execute_run()`：获取 conversation lock、标记 `running`、调用 adapter、写 assistant message / events / tool calls / results。
- `run_turn()`：兼容阶段 3，同步执行 `create_run()` + `execute_run()`。
- `cancel_run()`：写入取消请求，进行 best-effort cooperative cancellation。

## Workspace

每个用户会话有独立目录：

```text
.runtime_workspaces/
  user_<user_id>/
    conv_<conversation_id>/
      scratch/
      uploads/
      artifacts/
      traces/
```

workspace 路径不返回给前端。阶段 4 仍只建立目录边界；工具层更严格的文件访问限制留到后续阶段。

## 并发与后台任务

阶段 4 使用：

- in-process `threading.Lock` 防止同一 conversation 并发运行。
- FastAPI `BackgroundTasks` / in-process worker 执行异步 run。

这适合开发和单进程部署。生产环境应替换为队列系统和分布式锁，例如 Redis lock、Celery、RQ、Dramatiq 或 Arq。

## 测试策略

后端测试注入 fake adapter：

- 不真实调用 LLM。
- 不真实调用 bash/shell 工具。
- 不依赖外部网络。
- 验证 API、service、repository、事件持久化、SSE replay 和用户隔离。

