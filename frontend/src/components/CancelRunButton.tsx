import type { RunStatus } from '../types/run';

interface CancelRunButtonProps {
  runId: string | null;
  status: RunStatus | null;
  onCancel: () => Promise<void>;
}

export function CancelRunButton({ runId, status, onCancel }: CancelRunButtonProps) {
  const cancellable = Boolean(runId && (status === 'queued' || status === 'running' || status === 'cancelling'));
  if (!cancellable) {
    return null;
  }

  return (
    <button className="secondary danger" disabled={status === 'cancelling'} onClick={onCancel} type="button">
      {status === 'cancelling' ? 'Cancelling' : 'Cancel'}
    </button>
  );
}

