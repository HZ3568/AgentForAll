import type { Message } from '../types/message';
import type { RunEvent, RunStatus, ToolCallState } from '../types/run';

interface RunAttachedAction {
  type: 'run_attached';
  runId: string;
  anchorMessageId: string | null;
  status: RunStatus | null;
}

interface RunResetAction {
  type: 'run_reset';
}

interface RunStatusChangedAction {
  type: 'run_status_changed';
  status: RunStatus | null;
}

interface AssistantMessageConsumedAction {
  type: 'assistant_message_consumed';
}

interface EventReceivedAction {
  type: 'event_received';
  event: RunEvent;
}

interface ToolCallsLoadedAction {
  type: 'tool_calls_loaded';
  toolCalls: ToolCallState[];
}

export type RunAction =
  | RunAttachedAction
  | RunResetAction
  | RunStatusChangedAction
  | AssistantMessageConsumedAction
  | EventReceivedAction
  | ToolCallsLoadedAction;

export interface RunState {
  activeRunId: string | null;
  runAnchorMessageId: string | null;
  runStatus: RunStatus | null;
  events: RunEvent[];
  toolCalls: ToolCallState[];
  streamingText: string;
  pendingAssistantMessage: Message | null;
  error: string;
  processedSequenceNos: number[];
}

export function createInitialRunState(): RunState {
  return {
    activeRunId: null,
    runAnchorMessageId: null,
    runStatus: null,
    events: [],
    toolCalls: [],
    streamingText: '',
    pendingAssistantMessage: null,
    error: '',
    processedSequenceNos: [],
  };
}

export function runIsActive(status: RunStatus | null): boolean {
  return status === 'queued' || status === 'running' || status === 'cancelling';
}

export function runReducer(state: RunState, action: RunAction): RunState {
  if (action.type === 'run_reset') {
    return createInitialRunState();
  }
  if (action.type === 'run_status_changed') {
    return {
      ...state,
      activeRunId: action.status && runIsActive(action.status) ? state.activeRunId : null,
      runStatus: action.status,
      streamingText: action.status === 'cancelled' ? '' : state.streamingText,
    };
  }
  if (action.type === 'assistant_message_consumed') {
    return {
      ...state,
      pendingAssistantMessage: null,
    };
  }
  if (action.type === 'run_attached') {
    return {
      ...createInitialRunState(),
      activeRunId: action.runId,
      runAnchorMessageId: action.anchorMessageId,
      runStatus: action.status,
    };
  }
  if (action.type === 'tool_calls_loaded') {
    return {
      ...state,
      toolCalls: action.toolCalls,
    };
  }

  const event = action.event;
  if (state.processedSequenceNos.includes(event.sequence_no)) {
    return state;
  }

  const payload = asObject(event.event_json);
  const nextEvents = state.events.some((item) => item.sequence_no === event.sequence_no)
    ? state.events
    : [...state.events, event];
  const processedSequenceNos = [...state.processedSequenceNos, event.sequence_no];

  if (event.event_type === 'run_queued') {
    return { ...state, events: nextEvents, processedSequenceNos, runStatus: 'queued' };
  }
  if (event.event_type === 'run_started') {
    return { ...state, events: nextEvents, processedSequenceNos, runStatus: 'running' };
  }
  if (event.event_type === 'run_cancel_requested') {
    return { ...state, events: nextEvents, processedSequenceNos, runStatus: 'cancelling' };
  }
  if (event.event_type === 'run_cancelled') {
    return {
      ...state,
      activeRunId: null,
      events: nextEvents,
      processedSequenceNos,
      runStatus: 'cancelled',
      streamingText: '',
    };
  }
  if (event.event_type === 'run_failed') {
    return {
      ...state,
      activeRunId: null,
      error: typeof payload.message === 'string' ? payload.message : 'Agent run failed',
      events: nextEvents,
      processedSequenceNos,
      runStatus: 'failed',
    };
  }
  if (event.event_type === 'run_finished') {
    return {
      ...state,
      activeRunId: null,
      events: nextEvents,
      processedSequenceNos,
      runStatus: 'succeeded',
      streamingText: '',
    };
  }
  if (event.event_type === 'assistant_delta') {
    const delta = typeof payload.delta === 'string' ? payload.delta : typeof payload.text === 'string' ? payload.text : '';
    return {
      ...state,
      events: nextEvents,
      processedSequenceNos,
      streamingText: delta ? `${state.streamingText}${delta}` : state.streamingText,
    };
  }
  if (event.event_type === 'assistant_message_created') {
    return {
      ...state,
      events: nextEvents,
      pendingAssistantMessage: buildMessageFromEvent(event, payload),
      processedSequenceNos,
      streamingText: '',
    };
  }
  if (
    event.event_type === 'tool_call_started' ||
    event.event_type === 'tool_call_finished' ||
    event.event_type === 'tool_call_failed'
  ) {
    return {
      ...state,
      events: nextEvents,
      processedSequenceNos,
      toolCalls: upsertToolCall(state.toolCalls, payload),
    };
  }

  return { ...state, events: nextEvents, processedSequenceNos };
}

function buildMessageFromEvent(event: RunEvent, payload: Record<string, unknown>): Message | null {
  const messageId = typeof payload.message_id === 'string' ? payload.message_id : null;
  const contentText = typeof payload.content_text === 'string' ? payload.content_text : '';
  const role = payload.role === 'user' || payload.role === 'assistant' ? payload.role : 'assistant';
  const sequenceNo = typeof payload.sequence_no === 'number' ? payload.sequence_no : event.sequence_no;
  if (!messageId) {
    return null;
  }
  return {
    id: messageId,
    conversation_id: '',
    user_id: '',
    role,
    content_json: { type: 'text', text: contentText },
    content_text: contentText,
    token_count: null,
    sequence_no: sequenceNo,
    created_at: event.created_at,
  };
}

function upsertToolCall(items: ToolCallState[], payload: Record<string, unknown>): ToolCallState[] {
  const id = typeof payload.tool_call_id === 'string' ? payload.tool_call_id : null;
  const toolName = typeof payload.tool_name === 'string' ? payload.tool_name : 'tool';
  const status = typeof payload.status === 'string' ? payload.status : 'running';
  if (!id) {
    return items;
  }
  const existing = items.find((item) => item.id === id);
  if (!existing) {
    return [...items, { id, tool_name: toolName, status }];
  }
  return items.map((item) => (item.id === id ? { ...item, tool_name: toolName, status } : item));
}

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
