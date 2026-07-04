import type { AgentToolCall } from '../types/agent';

interface ToolCallSummaryProps {
  toolCalls: AgentToolCall[];
}

export function ToolCallSummary({ toolCalls }: ToolCallSummaryProps) {
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

