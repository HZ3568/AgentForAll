import { useEffect, useRef } from 'react';
import { apiUrl, getToken } from '../api/client';
import type { RunEvent } from '../types/run';

interface UseRunEventsOptions {
  enabled: boolean;
  afterSequenceNo?: number;
  onEvent: (event: RunEvent) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

export function useRunEvents(runId: string | null, options: UseRunEventsOptions) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    if (!runId || !options.enabled) {
      return undefined;
    }

    const abortController = new AbortController();
    let buffer = '';
    const after = options.afterSequenceNo ? `?after_sequence_no=${options.afterSequenceNo}` : '';

    async function connect() {
      try {
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
              optionsRef.current.onEvent(event);
            }
          }
        }
        optionsRef.current.onDone?.();
      } catch (error) {
        if (!abortController.signal.aborted) {
          optionsRef.current.onError?.(error instanceof Error ? error : new Error('Event stream failed'));
        }
      }
    }

    connect();
    return () => abortController.abort();
  }, [runId, options.enabled, options.afterSequenceNo]);
}

function parseSseFrame(frame: string): RunEvent | null {
  const dataLines: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  const data = JSON.parse(dataLines.join('\n')) as RunEvent | { event_type?: string };
  if (data.event_type === 'heartbeat') {
    return null;
  }
  return data as RunEvent;
}

