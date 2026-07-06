import { Activity, Brain, FileText, Wrench, type LucideIcon } from 'lucide-react';
import { useState } from 'react';
import type { WorkspaceFile } from '../types/conversation';
import type { RunEvent, RunStatus, ToolCallState } from '../types/run';
import { RunEventTimeline } from './RunEventTimeline';
import { RunStatusBadge } from './RunStatusBadge';

type WorkbenchTab = 'run' | 'tools' | 'files' | 'memory';

interface AgentWorkbenchProps {
  activeRunId: string | null;
  memoryIndex: string | null;
  runEvents: RunEvent[];
  runStatus: RunStatus | null;
  toolCalls: ToolCallState[];
  workspaceFiles: WorkspaceFile[];
}

const TABS: Array<{ id: WorkbenchTab; label: string; icon: LucideIcon }> = [
  { id: 'run', label: 'Run', icon: Activity },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'files', label: 'Files', icon: FileText },
  { id: 'memory', label: 'Memory', icon: Brain },
];

export function AgentWorkbench({
  activeRunId,
  memoryIndex,
  runEvents,
  runStatus,
  toolCalls,
  workspaceFiles,
}: AgentWorkbenchProps) {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('run');

  return (
    <aside className="workbench">
      <div className="workbench-tabs" role="tablist" aria-label="Agent workbench">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              aria-selected={activeTab === tab.id}
              className={activeTab === tab.id ? 'workbench-tab active' : 'workbench-tab'}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              type="button"
            >
              <Icon aria-hidden="true" size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
      <div className="workbench-panel" role="tabpanel">
        {activeTab === 'run' && (
          <div className="workbench-section">
            <div className="workbench-header">
              <span>{activeRunId ? activeRunId.slice(0, 8) : 'No active run'}</span>
              <RunStatusBadge status={runStatus} />
            </div>
            <RunEventTimeline events={runEvents} status={runStatus} />
            {runEvents.length === 0 && <p className="muted">No run events.</p>}
          </div>
        )}
        {activeTab === 'tools' && (
          <div className="workbench-section">
            {toolCalls.length === 0 && <p className="muted">No tool calls.</p>}
            {toolCalls.map((toolCall) => (
              <article className={`tool-detail ${toolCall.status}`} key={toolCall.id}>
                <div className="tool-detail-header">
                  <strong>{toolCall.tool_name}</strong>
                  <small>{toolCall.status}</small>
                </div>
                {toolCall.tool_input_json ? (
                  <pre>{JSON.stringify(toolCall.tool_input_json, null, 2)}</pre>
                ) : null}
                {toolCall.output_text ? <p>{toolCall.output_text}</p> : null}
              </article>
            ))}
          </div>
        )}
        {activeTab === 'files' && (
          <div className="workbench-section">
            {workspaceFiles.length === 0 && <p className="muted">No workspace files.</p>}
            {workspaceFiles.map((file) => (
              <article className="workspace-file" key={file.relative_path}>
                <span>{file.filename}</span>
                <small>
                  {file.section} · {formatBytes(file.size_bytes)}
                </small>
              </article>
            ))}
          </div>
        )}
        {activeTab === 'memory' && (
          <div className="workbench-section">
            {memoryIndex ? <pre className="memory-index">{memoryIndex}</pre> : <p className="muted">No memory index.</p>}
          </div>
        )}
      </div>
    </aside>
  );
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
