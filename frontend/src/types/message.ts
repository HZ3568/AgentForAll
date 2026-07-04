export interface Message {
  id: string;
  conversation_id: string;
  user_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content_json: unknown;
  content_text: string;
  token_count: number | null;
  sequence_no: number;
  created_at: string;
}

export interface MessageListResponse {
  items: Message[];
}
