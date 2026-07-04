import type { ToolCallState } from '../types/run';

interface ToolCallTimelineProps {
  toolCalls: ToolCallState[];
}

export function ToolCallTimeline({ toolCalls }: ToolCallTimelineProps) {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="tool-summary">
      {toolCalls.map((toolCall) => (
        <span className={`tool-call ${toolCall.status}`} key={toolCall.id}>
          {toolCall.tool_name} · {toolCall.status}
        </span>
      ))}
    </div>
  );
}

