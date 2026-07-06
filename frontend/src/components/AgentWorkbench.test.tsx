import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AgentWorkbench } from './AgentWorkbench';
import type { WorkspaceFilePreview } from '../types/conversation';

function renderWorkbench(preview: WorkspaceFilePreview | null = null) {
  const onTogglePanel = vi.fn();
  render(
    <AgentWorkbench
      onTogglePanel={onTogglePanel}
      panelOpen
      preview={preview}
      previewBlobUrl={null}
      previewError={null}
      previewLoading={false}
    />,
  );
  return onTogglePanel;
}

describe('AgentWorkbench', () => {
  it('renders a presentation-only panel without diagnostic tabs', async () => {
    const user = userEvent.setup();
    const onTogglePanel = renderWorkbench();

    expect(screen.getByLabelText('工件展示栏')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: '运行' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: '工具' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: '文件' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: '记忆' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '关闭展示栏' }));
    expect(onTogglePanel).toHaveBeenCalledOnce();
  });

  it('does not render a collapsed rail when the panel is closed', () => {
    render(
      <AgentWorkbench
        onTogglePanel={vi.fn()}
        panelOpen={false}
        preview={null}
        previewBlobUrl={null}
        previewError={null}
        previewLoading={false}
      />,
    );

    expect(screen.queryByLabelText('工件展示栏')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '打开工件面板' })).not.toBeInTheDocument();
  });

  it('renders text previews inside the artifact panel', async () => {
    const preview: WorkspaceFilePreview = {
      relative_path: 'artifacts/notes.md',
      filename: 'notes.md',
      preview_type: 'markdown',
      media_type: 'text/markdown',
      content: '# Notes\n\nhello',
      html: null,
      size_bytes: 18,
      error_message: null,
    };

    renderWorkbench(preview);

    expect(screen.getByText(/# Notes/)).toBeInTheDocument();
    expect(screen.getByText(/hello/)).toBeInTheDocument();
  });

  it('renders docx previews in a sandbox iframe', () => {
    const preview: WorkspaceFilePreview = {
      relative_path: 'artifacts/paper.docx',
      filename: 'paper.docx',
      preview_type: 'docx_html',
      media_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      content: null,
      html: '<h1>Paper</h1>',
      size_bytes: 1024,
      error_message: null,
    };

    renderWorkbench(preview);

    const frame = screen.getByTitle('paper.docx preview');
    expect(frame).toHaveAttribute('sandbox');
    expect(frame).toHaveAttribute('srcdoc', expect.stringContaining('<h1>Paper</h1>'));
  });
});
