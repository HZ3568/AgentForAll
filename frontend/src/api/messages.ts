import { apiRequest } from './client';
import type { Message, MessageListResponse } from '../types/message';

export async function listMessages(conversationId: string): Promise<Message[]> {
  const response = await apiRequest<MessageListResponse>(`/conversations/${conversationId}/messages`);
  return response.items;
}

export async function sendMessage(conversationId: string, content: string): Promise<Message> {
  return apiRequest<Message>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}
