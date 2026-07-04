export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
}

export interface ConversationListResponse {
  items: Conversation[];
}
