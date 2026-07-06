import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { ChatWindow } from './ChatWindow';

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

function renderChatWindow(onSend = vi.fn().mockResolvedValue(undefined)) {
  render(
    <ChatWindow
      activeRunId={null}
      conversation={null}
      loadingMessages={false}
      messages={[]}
      onCancelRun={vi.fn()}
      onPreviewWorkspaceFile={vi.fn()}
      onSend={onSend}
      runAnchorMessageId={null}
      runIsActive={false}
      runStatus={null}
      streamingText=""
    />,
  );
  return onSend;
}

describe('ChatWindow', () => {
  it('shows a centered Chinese welcome state for an empty chat', () => {
    renderChatWindow();

    expect(screen.getByText('嗨，今天做点什么？')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 "/" 唤起插件和技能')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '文档' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '网站' })).toBeInTheDocument();
  });

  it('sends one message with web search enabled and resets the toggle', async () => {
    const user = userEvent.setup();
    const onSend = renderChatWindow();

    const addButton = screen.getByRole('button', { name: '添加附件和工具' });
    expect(screen.queryByRole('button', { name: '网页搜索' })).not.toBeInTheDocument();

    await user.click(addButton);
    expect(addButton).toHaveAttribute('aria-expanded', 'true');

    const searchToggle = screen.getByRole('button', { name: '网页搜索' });
    await user.click(searchToggle);
    expect(searchToggle).toHaveAttribute('aria-pressed', 'true');

    await user.type(screen.getByPlaceholderText('输入 "/" 唤起插件和技能'), '今年高考本科分数线');
    await user.click(screen.getByRole('button', { name: '发送' }));

    expect(onSend).toHaveBeenCalledWith('今年高考本科分数线', { webSearchEnabled: true });
    await waitFor(() => expect(addButton).toHaveAttribute('aria-expanded', 'false'));
    await user.click(addButton);
    expect(screen.getByRole('button', { name: '网页搜索' })).toHaveAttribute('aria-pressed', 'false');
  });
});
