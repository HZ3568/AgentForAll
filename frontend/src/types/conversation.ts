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

export interface WorkspaceFile {
  relative_path: string;
  section: 'uploads' | 'artifacts' | 'traces' | string;
  filename: string;
  size_bytes: number;
  updated_at: string;
}

export interface WorkspaceFileListResponse {
  items: WorkspaceFile[];
}

export interface MemoryIndexResponse {
  content: string | null;
}
