import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ConversationSidebar } from './ConversationSidebar';
import type { Conversation } from '../types/conversation';

const conversation: Conversation = {
  id: 'conversation-1',
  user_id: 'user-1',
  title: 'Important chat',
  status: 'active',
  created_at: '2026-07-05T00:00:00Z',
  updated_at: '2026-07-05T00:00:00Z',
  last_message_at: null,
};

describe('ConversationSidebar', () => {
  it('confirms deletion in-app before calling onDelete', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <ConversationSidebar
        conversations={[conversation]}
        selectedId={conversation.id}
        user={{
          id: 'user-1',
          username: 'alice',
          email: 'alice@example.com',
          role: 'user',
          status: 'active',
          created_at: '2026-07-05T00:00:00Z',
          updated_at: '2026-07-05T00:00:00Z',
        }}
        onCreate={vi.fn()}
        onDelete={onDelete}
        deletingId={null}
        onSelect={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '新建会话' })).toBeInTheDocument();
    expect(screen.getByText('插件')).toBeInTheDocument();
    expect(screen.getByText('定时任务')).toBeInTheDocument();
    expect(screen.getByText('更多')).toBeInTheDocument();

    await user.click(screen.getByLabelText('删除 Important chat'));

    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toHaveTextContent('删除这个对话？');

    await user.click(screen.getByRole('button', { name: '删除' }));

    expect(onDelete).toHaveBeenCalledWith(conversation);
  });
});
