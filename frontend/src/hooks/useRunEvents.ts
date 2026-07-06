import { useEffect, useRef } from 'react';
import { apiUrl, getToken } from '../api/client';
import type { RunEvent } from '../types/run';
import { parseSseFrame } from '../utils/sseParser';

interface UseRunEventsOptions {
  enabled: boolean;
  afterSequenceNo?: number;
  onEvent: (event: RunEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

export function useRunEvents(runId: string | null, options: UseRunEventsOptions) {
  const optionsRef = useRef(options);
  const lastSequenceNoRef = useRef(0);
  optionsRef.current = options;

  useEffect(() => {
    lastSequenceNoRef.current = options.afterSequenceNo ?? 0;
  }, [runId, options.afterSequenceNo]);

  useEffect(() => {
    if (!runId || !options.enabled) {
      return undefined;
    }

    const abortController = new AbortController();
    let buffer = '';
    let attempts = 0;

    async function connect() {
      try {
        while (!abortController.signal.aborted) {
          const afterSequenceNo = optionsRef.current.afterSequenceNo ?? lastSequenceNoRef.current;
          const after = afterSequenceNo ? `?after_sequence_no=${afterSequenceNo}` : '';
          const token = getToken();
          const headers = new Headers();
          if (token) {
            headers.set('Authorization', `Bearer ${token}`);
          }
          const response = await fetch(apiUrl(`/agent/runs/${runId}/events/stream${after}`), {
            headers,
            signal: abortController.signal,
          });
          if (!response.ok || !response.body) {
            throw new Error(`Event stream failed with ${response.status}`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }
            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split(/\r?\n\r?\n/);
            buffer = frames.pop() ?? '';
            for (const frame of frames) {
              const event = parseSseFrame(frame);
              if (event) {
                lastSequenceNoRef.current = Math.max(lastSequenceNoRef.current, event.sequence_no);
                optionsRef.current.onEvent(event);
              }
            }
          }
          optionsRef.current.onDone?.();
          return;
        }
      } catch (error) {
        if (!abortController.signal.aborted) {
          attempts += 1;
          if (attempts <= 3) {
            await delay(400 * attempts);
            return connect();
          }
          optionsRef.current.onError?.(error instanceof Error ? error : new Error('Event stream failed'));
        }
      }
    }

    connect();
    return () => abortController.abort();
  }, [runId, options.enabled, options.afterSequenceNo]);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
