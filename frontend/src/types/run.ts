import type { Message } from './message';

export type RunStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'waiting_permission'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export interface RunCreateResponse {
  run_id: string;
  conversation_id: string;
  status: RunStatus;
  user_message: Message;
  events_url: string;
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

export interface RunEvent {
  id?: string;
  run_id?: string;
  sequence_no: number;
  event_type: string;
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
}

