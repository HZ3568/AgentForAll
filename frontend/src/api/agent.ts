import { apiRequest } from './client';
import type { AgentTurnResponse } from '../types/agent';

export async function runAgentTurn(conversationId: string, content: string): Promise<AgentTurnResponse> {
  return apiRequest<AgentTurnResponse>(`/agent/conversations/${conversationId}/turn`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

