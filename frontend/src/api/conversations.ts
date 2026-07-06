import { apiRequest } from './client';
import type {
  Conversation,
  ConversationListResponse,
  MemoryIndexResponse,
  WorkspaceFile,
  WorkspaceFileListResponse,
} from '../types/conversation';

export async function listConversations(): Promise<Conversation[]> {
  const response = await apiRequest<ConversationListResponse>('/conversations');
  return response.items;
}

export async function createConversation(title: string): Promise<Conversation> {
  return apiRequest<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export async function updateConversationTitle(id: string, title: string): Promise<Conversation> {
  return apiRequest<Conversation>(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(id: string): Promise<void> {
  await apiRequest<void>(`/conversations/${id}`, { method: 'DELETE' });
}

export async function listWorkspaceFiles(conversationId: string): Promise<WorkspaceFile[]> {
  const response = await apiRequest<WorkspaceFileListResponse>(`/conversations/${conversationId}/workspace-files`);
  return response.items;
}

export async function getMemoryIndex(conversationId: string): Promise<string | null> {
  const response = await apiRequest<MemoryIndexResponse>(`/conversations/${conversationId}/memory-index`);
  return response.content;
}
