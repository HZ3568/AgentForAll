import type { ToolCallState } from '../types/run';

interface ToolCallTimelineProps {
  toolCalls: ToolCallState[];
}

export function ToolCallTimeline({ toolCalls }: ToolCallTimelineProps) {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="tool-timeline">
      <div className="tool-timeline-title">Tools</div>
      {toolCalls.map((toolCall) => (
        <span className={`tool-call ${toolCall.status}`} key={toolCall.id}>
          <span>{toolCall.tool_name}</span>
          <small>{toolCall.status}</small>
        </span>
      ))}
    </div>
  );
}
