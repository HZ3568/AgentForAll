import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MessageContent } from './MessageBubble';

describe('MessageContent', () => {
  it('renders markdown paragraphs, lists, tables, and code blocks', () => {
    render(
      <MessageContent
        text={[
          '**Result**',
          '',
          '- item one',
          '',
          '| A | B |',
          '| - | - |',
          '| 1 | 2 |',
          '',
          '```ts',
          'const value = 1;',
          '```',
        ].join('\n')}
      />,
    );

    expect(screen.getByText('Result').tagName.toLowerCase()).toBe('strong');
    expect(screen.getByText('item one').closest('li')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('const value = 1;')).toBeInTheDocument();
  });

  it('routes workspace links to the artifact preview callback', async () => {
    const user = userEvent.setup();
    const onPreviewWorkspaceFile = vi.fn();
    render(
      <MessageContent
        onPreviewWorkspaceFile={onPreviewWorkspaceFile}
        text="[查看文档](artifacts/notes.md)"
      />,
    );

    await user.click(screen.getByRole('link', { name: '查看文档' }));

    expect(onPreviewWorkspaceFile).toHaveBeenCalledWith('artifacts/notes.md');
  });

  it('does not intercept external links', async () => {
    const user = userEvent.setup();
    const onPreviewWorkspaceFile = vi.fn();
    render(
      <MessageContent
        onPreviewWorkspaceFile={onPreviewWorkspaceFile}
        text="[OpenAI](https://openai.com)"
      />,
    );

    await user.click(screen.getByRole('link', { name: 'OpenAI' }));

    expect(onPreviewWorkspaceFile).not.toHaveBeenCalled();
  });
});
