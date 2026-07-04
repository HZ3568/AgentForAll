# Agent Runtime Adapter

阶段 3 使用 `AgentRuntimeAdapter` 把 FastAPI 后端和 `codeagent` Runtime 解耦。

## 边界

- `codeagent` 不 import `backend`。
- `codeagent` 不知道 FastAPI、MySQL、SQLAlchemy、JWT 或 React。
- API router 不直接调用 `codeagent`。
- backend 中只有 runtime adapter 直接 import `codeagent`。
- service 层负责事务、权限和持久化。

## 为什么需要 Adapter

`codeagent.core.loop.agent_loop(runtime, messages, context)` 是 CLI 已使用的核心循环。它会原地修改 `messages`，追加 assistant 消息和工具结果消息。Web 层需要复用这个能力，但不能把 HTTP、数据库或用户隔离逻辑塞进 Agent Loop。

`AgentRuntimeAdapter` 的职责是：

1. 将 MySQL 中的 messages 转换为 codeagent history。
2. 创建 codeagent runtime。
3. 调用 `agent_loop`。
4. 对比调用前后的 history，提取新增 assistant messages。
5. 提取 tool_use 和 tool_result。
6. 返回 backend 内部的 `AgentTurnResult`。

## Agent Turn 生命周期

`AgentService` 执行一次 turn：

1. 校验 conversation 属于当前用户。
2. 获取进程内 conversation lock。
3. 写入 user message。
4. 创建 agent run，标记 `running`。
5. 写入 `run_started`。
6. 调用 `AgentSessionManager` 和 `AgentRuntimeAdapter`。
7. 写入 assistant message。
8. 写入 adapter events。
9. 写入 tool calls 和 tool results。
10. 成功时写入 `run_finished` 并标记 `succeeded`。
11. 失败时写入 `run_failed` 并标记 `failed`。

失败时保留 user message 和 failed run，方便审计和前端展示。

## Workspace

`AgentSessionManager` 为每个用户会话准备：

```text
.runtime_workspaces/
  user_<user_id>/
    conv_<conversation_id>/
      scratch/
      uploads/
      artifacts/
      traces/
```

workspace 路径不返回给前端。阶段 3 先建立目录边界，后续需要加强工具层文件访问控制。

## 并发

阶段 3 使用进程内 `threading.Lock`，按 `user_id + conversation_id` 防止同一会话并发运行。该方案适合单进程开发环境。生产多进程部署需要 Redis lock 或数据库锁。

## 测试策略

后端测试注入 fake adapter：

- 不真实调用 LLM。
- 不真实调用 shell 工具。
- 不依赖外部网络。
- 验证 API、service、repository、持久化和用户隔离。

## 阶段 3 限制

- 非流式接口。
- 暂不实现 SSE 或 WebSocket。
- 暂不实现 cancel run。
- 暂不实现 permission_required 工具审批。
- 暂不实现 Memory 同步。

## 阶段 4 计划

- SSE 流式输出。
- 实时工具调用事件。
- run cancel。
- permission_required 工具审批。

