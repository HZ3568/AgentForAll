import type { RunStatus } from '../types/run';

interface RunStatusBadgeProps {
  status: RunStatus | null;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  if (!status) {
    return null;
  }

  return <span className={`run-status ${status}`}>{status}</span>;
}
