import { ChevronRight, Download, FileText } from 'lucide-react';
import type { WorkspaceFilePreview } from '../types/conversation';

interface AgentWorkbenchProps {
  onTogglePanel: () => void;
  panelOpen: boolean;
  preview: WorkspaceFilePreview | null;
  previewBlobUrl: string | null;
  previewError: string | null;
  previewLoading: boolean;
}

export function AgentWorkbench({
  onTogglePanel,
  panelOpen,
  preview,
  previewBlobUrl,
  previewError,
  previewLoading,
}: AgentWorkbenchProps) {
  if (!panelOpen) {
    return null;
  }

  return (
    <aside className="workbench artifact-panel" aria-label="工件展示栏">
      <header className="workbench-titlebar">
        <div>
          <strong>展示栏</strong>
          <span>点击会话中的工作区文件链接后在这里预览</span>
        </div>
        <button aria-label="关闭展示栏" className="icon-button" onClick={onTogglePanel} type="button">
          <ChevronRight aria-hidden="true" size={18} />
        </button>
      </header>
      <ArtifactPreview
        blobUrl={previewBlobUrl}
        error={previewError}
        loading={previewLoading}
        preview={preview}
      />
    </aside>
  );
}

interface ArtifactPreviewProps {
  blobUrl: string | null;
  error: string | null;
  loading: boolean;
  preview: WorkspaceFilePreview | null;
}

function ArtifactPreview({ blobUrl, error, loading, preview }: ArtifactPreviewProps) {
  if (loading) {
    return (
      <section className="artifact-preview">
        <p className="muted">正在加载预览...</p>
      </section>
    );
  }
  if (error) {
    return (
      <section className="artifact-preview">
        <p className="error">{error}</p>
      </section>
    );
  }
  if (!preview) {
    return (
      <section className="artifact-preview empty">
        <FileText aria-hidden="true" size={28} />
        <p className="muted">暂无预览内容。</p>
      </section>
    );
  }

  return (
    <section className="artifact-preview">
      <div className="artifact-preview-header">
        <div>
          <strong>{preview.filename}</strong>
          <small>{formatBytes(preview.size_bytes)}</small>
        </div>
        {blobUrl && (
          <a className="artifact-download" download={preview.filename} href={blobUrl}>
            <Download aria-hidden="true" size={15} />
            下载
          </a>
        )}
      </div>
      {preview.preview_type === 'text' || preview.preview_type === 'markdown' ? (
        <pre className="artifact-text-preview">{preview.content}</pre>
      ) : null}
      {preview.preview_type === 'docx_html' ? (
        <iframe
          className="artifact-doc-frame"
          sandbox=""
          srcDoc={buildDocxPreviewDocument(preview.html ?? '')}
          title={`${preview.filename} preview`}
        />
      ) : null}
      {preview.preview_type === 'pdf' && blobUrl ? (
        <iframe className="artifact-doc-frame" src={blobUrl} title={`${preview.filename} preview`} />
      ) : null}
      {preview.preview_type === 'image' && blobUrl ? (
        <img alt={preview.filename} className="artifact-image-preview" src={blobUrl} />
      ) : null}
      {preview.preview_type === 'download_only' ? (
        <p className="muted">
          {preview.error_message ?? '这个文件暂不支持内嵌预览，可下载后查看。'}
        </p>
      ) : null}
    </section>
  );
}

function buildDocxPreviewDocument(html: string): string {
  return [
    '<!doctype html>',
    '<html>',
    '<head>',
    '<meta charset="utf-8" />',
    '<base target="_blank" />',
    '<style>body{font-family:Inter,system-ui,sans-serif;line-height:1.65;margin:24px;color:#1f2937;}img{max-width:100%;height:auto;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #d1d5db;padding:6px 8px;}</style>',
    '</head>',
    '<body>',
    html,
    '</body>',
    '</html>',
  ].join('');
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
