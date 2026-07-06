import { describe, expect, it } from 'vitest';
import { parseSseFrame } from './sseParser';

describe('parseSseFrame', () => {
  it('parses run event payloads from SSE data frames', () => {
    const frame = [
      'id: 4',
      'event: assistant_delta',
      'data: {"run_id":"run-1","sequence_no":4,"event_type":"assistant_delta","event_json":{"delta":"hi"},"created_at":"2026-07-05T00:00:00Z"}',
    ].join('\n');

    const event = parseSseFrame(frame);

    expect(event).toEqual({
      run_id: 'run-1',
      sequence_no: 4,
      event_type: 'assistant_delta',
      event_json: { delta: 'hi' },
      created_at: '2026-07-05T00:00:00Z',
    });
  });

  it('ignores heartbeat frames', () => {
    expect(parseSseFrame('event: heartbeat\ndata: {"event_type":"heartbeat"}')).toBeNull();
  });
});
