import { apiRequest } from './client';
import type {
  RunCancelResponse,
  RunCreateResponse,
  RunCreateOptions,
  RunEventsResponse,
  RunListResponse,
  RunRead,
  RunToolCallsResponse,
} from '../types/run';

export async function createAgentRun(
  conversationId: string,
  content: string,
  options: RunCreateOptions = {},
): Promise<RunCreateResponse> {
  return apiRequest<RunCreateResponse>(`/agent/conversations/${conversationId}/runs`, {
    method: 'POST',
    body: JSON.stringify({
      content,
      web_search_enabled: Boolean(options.webSearchEnabled),
    }),
  });
}

export async function getAgentRun(runId: string): Promise<RunRead> {
  return apiRequest<RunRead>(`/agent/runs/${runId}`);
}

export async function listConversationRuns(
  conversationId: string,
  status: 'active' | undefined = undefined,
  limit = 10,
): Promise<RunRead[]> {
  const params = new URLSearchParams();
  if (status) {
    params.set('status', status);
  }
  params.set('limit', String(limit));
  const response = await apiRequest<RunListResponse>(`/agent/conversations/${conversationId}/runs?${params.toString()}`);
  return response.items;
}

export async function listRunEvents(runId: string, afterSequenceNo?: number): Promise<RunEventsResponse> {
  const search = afterSequenceNo ? `?after_sequence_no=${afterSequenceNo}` : '';
  return apiRequest<RunEventsResponse>(`/agent/runs/${runId}/events${search}`);
}

export async function listRunToolCalls(runId: string): Promise<RunToolCallsResponse> {
  return apiRequest<RunToolCallsResponse>(`/agent/runs/${runId}/tool-calls`);
}

export async function cancelAgentRun(runId: string): Promise<RunCancelResponse> {
  return apiRequest<RunCancelResponse>(`/agent/runs/${runId}/cancel`, {
    method: 'POST',
  });
}
