import { ApiError, apiRequest, apiUrl, getToken } from './client';
import type {
  Conversation,
  ConversationListResponse,
  MemoryIndexResponse,
  WorkspaceFile,
  WorkspaceFileListResponse,
  WorkspaceFilePreview,
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

export async function getWorkspaceFilePreview(
  conversationId: string,
  path: string,
): Promise<WorkspaceFilePreview> {
  const params = new URLSearchParams({ path });
  return apiRequest<WorkspaceFilePreview>(
    `/conversations/${conversationId}/workspace-files/preview?${params.toString()}`,
  );
}

export async function getWorkspaceFileBlob(conversationId: string, path: string): Promise<Blob> {
  const params = new URLSearchParams({ path });
  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(
    apiUrl(`/conversations/${conversationId}/workspace-files/raw?${params.toString()}`),
    { headers },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed';
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}

export async function getMemoryIndex(conversationId: string): Promise<string | null> {
  const response = await apiRequest<MemoryIndexResponse>(`/conversations/${conversationId}/memory-index`);
  return response.content;
}
