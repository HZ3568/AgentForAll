# Backend API

阶段 3 的 Web API 由 `backend` 提供。除健康检查外，用户私有资源都使用 JWT Bearer Token 鉴权，并且所有 conversation、message、run、tool 查询都绑定 `current_user.id`。

## 鉴权

请求头：

```http
Authorization: Bearer <token>
```

已实现：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

`register` 只保存 `password_hash`，任何响应都不返回密码哈希。

## Conversations

已实现：

- `GET /api/v1/conversations`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `PATCH /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`

所有操作都按 `current_user.id` 过滤。访问其他用户的会话统一返回 `404`，不暴露对象是否存在。

## Messages

已实现：

- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages`

普通 message API 仍可保存 `role=user` 消息。阶段 3 的正式对话入口是 Agent turn API，前端发送用户输入时应优先调用 Agent turn，而不是先单独写入 message。

## Agent Turn

已实现：

- `POST /api/v1/agent/conversations/{conversation_id}/turn`

请求：

```json
{
  "content": "帮我读取 README 并总结"
}
```

响应：

```json
{
  "run_id": "...",
  "status": "succeeded",
  "conversation_id": "...",
  "user_message": {"role": "user", "content_text": "..."},
  "assistant_messages": [{"role": "assistant", "content_text": "..."}],
  "events": [{"event_type": "run_started", "event_json": {}}],
  "tool_calls": [{"tool_name": "read_file", "status": "succeeded"}],
  "error": null
}
```

行为：

- 必须登录。
- `conversation_id` 必须属于当前用户，否则返回 `404`。
- content 不能为空。
- 同一 conversation 已有进程内运行锁时返回 `409`。
- API 内部创建 user message，不需要前端提前调用 message POST。
- 成功时写入 assistant message、agent run、run events、tool calls 和 tool results。
- Agent 执行失败时返回 `500`，但保留 user message 和 failed `agent_run`。

## 用户隔离

- Repository 查询 conversation/message/run/event/tool 时必须显式传入 `user_id`。
- `tool_results` 表内没有 `user_id`，访问和写入必须通过 `tool_calls.user_id` 校验。
- API 对跨用户访问返回 `404`，避免泄露资源存在性。

## 阶段 3 限制

- Agent turn 是非流式接口。
- 暂无 SSE 或 WebSocket。
- 暂无 run cancel。
- 暂无工具审批。
- 测试使用 fake adapter，不真实调用 LLM、shell 工具或外部网络。

## 阶段 4 计划

- SSE 流式输出。
- 实时工具调用事件。
- cancel run。
- permission_required 工具审批。
