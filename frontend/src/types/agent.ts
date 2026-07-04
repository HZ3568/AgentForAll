import type { Message } from './message';

export type AgentRunStatus =
  | 'queued'
  | 'running'
  | 'waiting_permission'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export interface AgentEvent {
  id: string;
  event_type: string;
  event_json: unknown;
  sequence_no: number;
  created_at: string;
}

export interface AgentToolCall {
  id: string;
  tool_name: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'denied';
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AgentTurnResponse {
  run_id: string;
  status: AgentRunStatus;
  conversation_id: string;
  user_message: Message;
  assistant_messages: Message[];
  events: AgentEvent[];
  tool_calls: AgentToolCall[];
  error: string | null;
}

