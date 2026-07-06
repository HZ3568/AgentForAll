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

    await user.click(screen.getByLabelText('Delete Important chat'));

    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toHaveTextContent('Delete conversation?');

    await user.click(screen.getByRole('button', { name: 'Delete' }));

    expect(onDelete).toHaveBeenCalledWith(conversation);
  });
});
