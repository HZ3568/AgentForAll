import { useCallback, useEffect, useReducer } from 'react';
import { cancelAgentRun, listConversationRuns, listRunToolCalls } from '../api/runs';
import { useRunEvents } from './useRunEvents';
import { createInitialRunState, runIsActive, runReducer } from '../state/runReducer';
import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import type { RunCreateResponse, ToolCallState } from '../types/run';

interface UseActiveRunOptions {
  conversation: Conversation | null;
  messages: Message[];
  user: User | null;
  appendMessageOnce: (message: Message) => void;
  onError: (message: string) => void;
  onRefreshConversations: () => Promise<unknown>;
}

export function useActiveRun({
  conversation,
  messages,
  user,
  appendMessageOnce,
  onError,
  onRefreshConversations,
}: UseActiveRunOptions) {
  const [state, dispatch] = useReducer(runReducer, undefined, createInitialRunState);
  const active = runIsActive(state.runStatus);

  const resetRunState = useCallback(() => {
    dispatch({ type: 'run_reset' });
  }, []);

  const recoverActiveRun = useCallback(async (messageSnapshot: Message[] = messages) => {
    if (!conversation) {
      resetRunState();
      return;
    }
    const runs = await listConversationRuns(conversation.id, 'active', 1);
    const run = runs[0];
    if (!run) {
      resetRunState();
      return;
    }
    const anchor = [...messageSnapshot].reverse().find((message) => message.role === 'user')?.id ?? null;
    dispatch({
      type: 'run_attached',
      runId: run.id,
      anchorMessageId: anchor,
      status: run.status,
    });
  }, [conversation, messages, resetRunState]);

  const attachCreatedRun = useCallback((response: RunCreateResponse) => {
    dispatch({
      type: 'run_attached',
      runId: response.run_id,
      anchorMessageId: response.user_message.id,
      status: response.status,
    });
  }, []);

  const cancelActiveRun = useCallback(async () => {
    if (!state.activeRunId) {
      return;
    }
    const response = await cancelAgentRun(state.activeRunId);
    dispatch({ type: 'run_status_changed', status: response.status });
  }, [state.activeRunId]);

  useRunEvents(state.activeRunId, {
    enabled: Boolean(state.activeRunId),
    onEvent: (event) => dispatch({ type: 'event_received', event }),
    onError: (err) => {
      onError(err.message);
      dispatch({ type: 'run_status_changed', status: 'failed' });
    },
  });

  useEffect(() => {
    if (!state.pendingAssistantMessage || !conversation || !user) {
      return;
    }
    appendMessageOnce({
      ...state.pendingAssistantMessage,
      conversation_id: conversation.id,
      user_id: user.id,
    });
    dispatch({ type: 'assistant_message_consumed' });
  }, [appendMessageOnce, conversation, state.pendingAssistantMessage, user]);

  useEffect(() => {
    if (state.runStatus === 'succeeded') {
      onRefreshConversations().catch(() => undefined);
    }
  }, [onRefreshConversations, state.runStatus]);

  useEffect(() => {
    if (!state.activeRunId) {
      return;
    }
    let cancelled = false;
    listRunToolCalls(state.activeRunId)
      .then((response) => {
        if (cancelled) {
          return;
        }
        const toolCalls: ToolCallState[] = response.items.map((item) => ({
          id: item.id,
          tool_name: item.tool_name,
          tool_input_json: item.tool_input_json,
          status: item.status,
          output_text: item.result?.output_text,
          error_type: item.result?.error_type,
          created_at: item.created_at,
          started_at: item.started_at,
          finished_at: item.finished_at,
        }));
        dispatch({ type: 'tool_calls_loaded', toolCalls });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [state.activeRunId, state.events.length]);

  return {
    activeRunId: state.activeRunId,
    attachCreatedRun,
    cancelActiveRun,
    recoverActiveRun,
    resetRunState,
    runAnchorMessageId: state.runAnchorMessageId,
    runEvents: state.events,
    runError: state.error,
    runIsActive: active,
    runStatus: state.runStatus,
    streamingText: state.streamingText,
    toolCalls: state.toolCalls,
  };
}
