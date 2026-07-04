import type { RunEvent, RunStatus } from '../types/run';

interface RunEventTimelineProps {
  events: RunEvent[];
  status: RunStatus | null;
}

const EVENT_LABELS: Record<string, string> = {
  run_queued: 'Queued',
  user_message_created: 'Message saved',
  run_started: 'Agent started',
  assistant_delta: 'Writing response',
  assistant_message_created: 'Response saved',
  tool_call_started: 'Tool started',
  tool_call_finished: 'Tool finished',
  tool_call_failed: 'Tool failed',
  tool_result_created: 'Tool result saved',
  run_cancel_requested: 'Cancel requested',
  run_cancelled: 'Cancelled',
  run_finished: 'Finished',
  run_failed: 'Failed',
};

export function RunEventTimeline({ events, status }: RunEventTimelineProps) {
  if (events.length === 0) {
    return null;
  }

  const visibleEvents = compactEvents(events);

  return (
    <div className="run-activity">
      <div className="run-activity-header">
        <span>Execution</span>
        {status && <span className={`run-activity-status ${status}`}>{status}</span>}
      </div>
      <ol className="run-events">
        {visibleEvents.map((event) => (
          <li className={eventClassName(event.event_type)} key={`${event.sequence_no}-${event.event_type}`}>
            <span className="run-event-dot" />
            <span>{EVENT_LABELS[event.event_type] ?? event.event_type}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function compactEvents(events: RunEvent[]): RunEvent[] {
  const compacted: RunEvent[] = [];
  let hasAssistantDelta = false;
  for (const event of events) {
    if (event.event_type === 'assistant_delta') {
      if (hasAssistantDelta) {
        continue;
      }
      hasAssistantDelta = true;
    }
    compacted.push(event);
  }
  return compacted.slice(-8);
}

function eventClassName(eventType: string): string {
  if (eventType === 'run_failed' || eventType === 'tool_call_failed') {
    return 'run-event failed';
  }
  if (eventType === 'run_finished' || eventType === 'assistant_message_created') {
    return 'run-event succeeded';
  }
  return 'run-event';
}
