import type { RunEvent } from '../types/run';

interface RunEventTimelineProps {
  events: RunEvent[];
}

export function RunEventTimeline({ events }: RunEventTimelineProps) {
  if (events.length === 0) {
    return null;
  }

  return (
    <div className="run-events">
      {events.slice(-8).map((event) => (
        <span className="run-event" key={`${event.sequence_no}-${event.event_type}`}>
          {event.sequence_no}. {event.event_type}
        </span>
      ))}
    </div>
  );
}

