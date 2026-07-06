import { describe, expect, it } from 'vitest';
import { createInitialRunState, runReducer } from './runReducer';

describe('runReducer', () => {
  it('accumulates streaming deltas and finalizes the saved assistant message', () => {
    const started = runReducer(
      createInitialRunState(),
      {
        type: 'run_attached',
        runId: 'run-1',
        anchorMessageId: 'message-1',
        status: 'running',
      },
    );
    const streaming = runReducer(started, {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 3,
        event_type: 'assistant_delta',
        event_json: { delta: 'hello ' },
        created_at: '2026-07-05T00:00:00Z',
      },
    });
    const saved = runReducer(streaming, {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 4,
        event_type: 'assistant_message_created',
        event_json: {
          message_id: 'assistant-1',
          role: 'assistant',
          content_text: 'hello world',
          sequence_no: 2,
        },
        created_at: '2026-07-05T00:00:01Z',
      },
    });

    expect(streaming.streamingText).toBe('hello ');
    expect(saved.streamingText).toBe('');
    expect(saved.pendingAssistantMessage?.id).toBe('assistant-1');
    expect(saved.pendingAssistantMessage?.content_text).toBe('hello world');
  });

  it('deduplicates replayed sequence numbers', () => {
    const state = runReducer(createInitialRunState(), {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 3,
        event_type: 'assistant_delta',
        event_json: { delta: 'hello' },
        created_at: '2026-07-05T00:00:00Z',
      },
    });

    const replayed = runReducer(state, {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 3,
        event_type: 'assistant_delta',
        event_json: { delta: 'hello' },
        created_at: '2026-07-05T00:00:00Z',
      },
    });

    expect(replayed.streamingText).toBe('hello');
    expect(replayed.events).toHaveLength(1);
  });

  it('keeps streamed text visible when a run fails before saving the assistant message', () => {
    const streaming = runReducer(createInitialRunState(), {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 3,
        event_type: 'assistant_delta',
        event_json: { delta: 'partial answer' },
        created_at: '2026-07-05T00:00:00Z',
      },
    });

    const failed = runReducer(streaming, {
      type: 'event_received',
      event: {
        run_id: 'run-1',
        sequence_no: 4,
        event_type: 'run_failed',
        event_json: { message: 'Agent produced no assistant message.' },
        created_at: '2026-07-05T00:00:01Z',
      },
    });

    expect(failed.runStatus).toBe('failed');
    expect(failed.error).toBe('Agent produced no assistant message.');
    expect(failed.streamingText).toBe('partial answer');
  });
});
