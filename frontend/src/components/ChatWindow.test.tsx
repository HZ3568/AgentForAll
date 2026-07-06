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
  it('sends one message with web search enabled and resets the toggle', async () => {
    const user = userEvent.setup();
    const onSend = renderChatWindow();

    const searchToggle = screen.getByRole('button', { name: '网页搜索' });
    await user.click(searchToggle);
    expect(searchToggle).toHaveAttribute('aria-pressed', 'true');

    await user.type(screen.getByPlaceholderText('Ask the agent...'), '今年高考本科分数线');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(onSend).toHaveBeenCalledWith('今年高考本科分数线', { webSearchEnabled: true });
    await waitFor(() => expect(searchToggle).toHaveAttribute('aria-pressed', 'false'));
  });
});
