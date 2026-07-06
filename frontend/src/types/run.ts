import type { Message } from './message';

export type RunStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'waiting_permission'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export type RunEventType =
  | 'run_queued'
  | 'run_started'
  | 'user_message_created'
  | 'assistant_delta'
  | 'assistant_message_created'
  | 'tool_call_started'
  | 'tool_call_finished'
  | 'tool_call_failed'
  | 'tool_result_created'
  | 'run_cancel_requested'
  | 'run_cancelled'
  | 'run_finished'
  | 'run_failed'
  | 'heartbeat';

export interface RunCreateResponse {
  run_id: string;
  conversation_id: string;
  status: RunStatus;
  user_message: Message;
  events_url: string;
}

export interface RunCreateOptions {
  webSearchEnabled?: boolean;
}

export interface RunRead {
  id: string;
  conversation_id: string;
  status: RunStatus;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RunListResponse {
  items: RunRead[];
}

export interface RunEvent {
  id?: string;
  run_id?: string;
  sequence_no: number;
  event_type: RunEventType | string;
  event_json: Record<string, unknown> | unknown[] | null;
  created_at: string;
}

export interface RunEventsResponse {
  run_id: string;
  events: RunEvent[];
}

export interface RunCancelResponse {
  run_id: string;
  status: RunStatus;
}

export interface ToolCallState {
  id: string;
  tool_name: string;
  status: string;
  output_text?: string | null;
  error_type?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  tool_input_json?: Record<string, unknown> | unknown[] | null;
}

export interface ToolResultDetail {
  id: string;
  output_text: string | null;
  output_json: Record<string, unknown> | unknown[] | null;
  evidence_json: Record<string, unknown> | unknown[] | null;
  error_type: string | null;
  created_at: string;
}

export interface ToolCallDetail {
  id: string;
  tool_name: string;
  tool_input_json: Record<string, unknown> | unknown[] | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  result: ToolResultDetail | null;
}

export interface RunToolCallsResponse {
  run_id: string;
  items: ToolCallDetail[];
}
