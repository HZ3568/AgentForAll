# Streaming Events

阶段 4 使用 SSE 实现 Agent run 的实时事件输出，不使用 WebSocket。

## 为什么使用 SSE

当前需求是服务器单向推送 run events。SSE 更简单，天然支持文本事件、断线重连语义和 HTTP 基础设施。WebSocket 留给双向实时控制场景；阶段 4 暂不需要。

## 接口

- `POST /api/v1/agent/conversations/{conversation_id}/runs`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/runs/{run_id}/events`
- `GET /api/v1/agent/runs/{run_id}/events/stream`
- `POST /api/v1/agent/runs/{run_id}/cancel`

SSE 格式：

```text
event: assistant_delta
id: 4
data: {"run_id":"...","sequence_no":4,"event_type":"assistant_delta","event_json":{"delta":"..."}}
```

## 事件类型

- `run_queued`
- `run_started`
- `user_message_created`
- `assistant_delta`
- `assistant_message_created`
- `tool_call_started`
- `tool_call_finished`
- `tool_call_failed`
- `tool_result_created`
- `run_cancel_requested`
- `run_cancelled`
- `run_finished`
- `run_failed`
- `heartbeat`

`message` 相关事件包含 `message_id`、`role` 和 `content_text` 或 `delta`。`tool` 相关事件包含 `tool_call_id`、`tool_name` 和 `status`。`run_failed` 只包含可展示的简短错误，不包含 traceback、密钥或环境变量。

## 持久化原则

MySQL 是权威状态：

- run 状态写入 `agent_runs`。
- 事件写入 `run_events`。
- SSE 从 `run_events` 读取事件并输出。
- 断线重连只回放数据库已有事件，不重复写事件。

## 断线重连

客户端记录最后收到的 `sequence_no`，重连时传：

```http
GET /api/v1/agent/runs/{run_id}/events/stream?after_sequence_no=12
```

服务端先补发 `after_sequence_no` 之后的数据库事件。如果 run 已经是 `succeeded/failed/cancelled`，补发完成后关闭连接。

## 鉴权

SSE 仍使用：

```http
Authorization: Bearer <token>
```

前端使用 `fetch + ReadableStream` 解析 SSE，因为原生 `EventSource` 不能设置 Authorization header。不把 JWT 放到 URL query，避免被浏览器历史、代理和服务日志泄露。

## Cancel Run

阶段 4 的取消是 best-effort cooperative cancellation：

- queued run 可以直接取消。
- running run 会写入 `run_cancel_requested` 并标记 `cancelling`。
- 当前不强杀 Python 线程，也不强制中断正在执行的 LLM/tool。
- adapter 返回后如果 run 已被标记 cancelling，则最终写入 `run_cancelled`。

## 当前限制

- in-process background task。
- in-process lock。
- 单进程开发友好。
- 生产环境需要 Redis / queue / distributed lock。
- 开发环境不要用裸 `uvicorn backend.app.main:app --reload` 监听整个仓库；Agent 写入 `.runtime_workspaces/` 会触发 reload。使用 `python scripts/dev_backend.py` 或显式设置 `--reload-dir backend --reload-dir codeagent`。

## 阶段 5 计划

- 工具权限审批 `permission_required`。
- 文件上传和 workspace 文件管理。
- 更严格的工具沙箱。
- Run 恢复与任务队列。
