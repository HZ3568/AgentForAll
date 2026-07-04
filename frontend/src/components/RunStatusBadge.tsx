import type { AgentRunStatus } from '../types/agent';

interface RunStatusBadgeProps {
  status: AgentRunStatus | null;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  if (!status) {
    return null;
  }

  return <span className={`run-status ${status}`}>{status}</span>;
}

