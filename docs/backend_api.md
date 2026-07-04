# Backend API

Backend API 由 `backend` 提供。除健康检查外，用户私有资源都使用 JWT Bearer Token 鉴权，并且所有 conversation、message、run、event、tool 查询都绑定 `current_user.id`。

## 鉴权

```http
Authorization: Bearer <token>
```

已实现：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

`register` 只保存 `password_hash`，任何响应都不返回密码哈希。

## Conversations

- `GET /api/v1/conversations`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `PATCH /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`

所有操作都按 `current_user.id` 过滤。访问其他用户的会话统一返回 `404`。

## Messages

- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages`

普通 message API 仍可保存 `role=user` 消息。前端正式对话应优先调用 Agent Run API，不要先单独写入 message。

## Non-Streaming Turn

阶段 3 接口保留：

- `POST /api/v1/agent/conversations/{conversation_id}/turn`

该接口同步执行一次 Agent turn，等待 assistant message 完整生成后返回。它仍会写入 user message、assistant message、agent run、run events、tool calls 和 tool results。

## Async Runs

阶段 4 新增：

- `POST /api/v1/agent/conversations/{conversation_id}/runs`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/runs/{run_id}/events`
- `GET /api/v1/agent/runs/{run_id}/events/stream`
- `POST /api/v1/agent/runs/{run_id}/cancel`

创建 run：

```json
{
  "content": "帮我读取 README 并总结"
}
```

响应：

```json
{
  "run_id": "...",
  "conversation_id": "...",
  "status": "queued",
  "user_message": {"role": "user", "content_text": "..."},
  "events_url": "/api/v1/agent/runs/{run_id}/events/stream"
}
```

行为：

- 必须登录。
- conversation 必须属于当前用户。
- content 不能为空。
- API 快速返回，不等待 Agent 完整执行。
- 后台 worker 执行 run，并持续写入 `run_events`；`assistant_delta` 是后端 LLM streaming chunk，不是前端模拟。
- 同一 conversation 已有 `queued/running/cancelling` run 时返回 `409`。

## Event Replay

查询事件：

```http
GET /api/v1/agent/runs/{run_id}/events?after_sequence_no=3&limit=200
```

响应：

```json
{
  "run_id": "...",
  "events": [
    {
      "sequence_no": 4,
      "event_type": "assistant_delta",
      "event_json": {"delta": "..."},
      "created_at": "..."
    }
  ]
}
```

SSE 使用同一批数据库事件作为来源。`after_sequence_no` 用于断线重连和页面恢复。

## Cancel Run

```http
POST /api/v1/agent/runs/{run_id}/cancel
```

阶段 4 是 best-effort cooperative cancellation：

- queued run 可以直接变成 `cancelled`。
- running run 会先标记 `cancelling` 并写入 `run_cancel_requested`。
- 当前 adapter 无法强制中断正在执行的 LLM/tool。
- 不强杀线程。

## 用户隔离

- Repository 查询 conversation/message/run/event/tool 时必须显式传入 `user_id`。
- `tool_results` 表内没有 `user_id`，访问和写入必须通过 `tool_calls.user_id` 校验。
- API 对跨用户访问返回 `404`，避免泄露资源存在性。
