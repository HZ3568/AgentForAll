import type { RunEvent } from '../types/run';

export function parseSseFrame(frame: string): RunEvent | null {
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
