import { apiRequest } from './client';
import type { RunCancelResponse, RunCreateResponse, RunEventsResponse, RunRead } from '../types/run';

export async function createAgentRun(conversationId: string, content: string): Promise<RunCreateResponse> {
  return apiRequest<RunCreateResponse>(`/agent/conversations/${conversationId}/runs`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export async function getAgentRun(runId: string): Promise<RunRead> {
  return apiRequest<RunRead>(`/agent/runs/${runId}`);
}

export async function listRunEvents(runId: string, afterSequenceNo?: number): Promise<RunEventsResponse> {
  const search = afterSequenceNo ? `?after_sequence_no=${afterSequenceNo}` : '';
  return apiRequest<RunEventsResponse>(`/agent/runs/${runId}/events${search}`);
}

export async function cancelAgentRun(runId: string): Promise<RunCancelResponse> {
  return apiRequest<RunCancelResponse>(`/agent/runs/${runId}/cancel`, {
    method: 'POST',
  });
}

