import { LogOut, MessageSquarePlus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';

interface ConversationSidebarProps {
  conversations: Conversation[];
  selectedId: string | null;
  user: User | null;
  onCreate: () => void;
  onDelete: (conversation: Conversation) => void | Promise<void>;
  deletingId: string | null;
  onSelect: (conversation: Conversation) => void;
  onLogout: () => void;
}

export function ConversationSidebar({
  conversations,
  selectedId,
  user,
  onCreate,
  onDelete,
  deletingId,
  onSelect,
  onLogout,
}: ConversationSidebarProps) {
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null);

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    await onDelete(pendingDelete);
    setPendingDelete(null);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-account">
        <div className="brand-mark">A</div>
        <div>
          <h2>AgentForAll</h2>
          <p>{user ? user.email : 'Loading user...'}</p>
        </div>
      </div>
      <button className="new-chat-button" onClick={onCreate} type="button">
        <MessageSquarePlus aria-hidden="true" size={17} />
        <span>New chat</span>
      </button>
      <nav className="conversation-list">
        {conversations.map((conversation) => (
          <div
            className={conversation.id === selectedId ? 'conversation active' : 'conversation'}
            key={conversation.id}
          >
            <button
              aria-current={conversation.id === selectedId ? 'page' : undefined}
              className="conversation-main"
              onClick={() => onSelect(conversation)}
              title={conversation.title}
              type="button"
            >
              <span>{conversation.title}</span>
              <small>{formatConversationMeta(conversation)}</small>
            </button>
            <button
              aria-label={`Delete ${conversation.title}`}
              className="conversation-delete"
              disabled={deletingId === conversation.id}
              onClick={() => setPendingDelete(conversation)}
              title="Delete conversation"
              type="button"
            >
              <Trash2 aria-hidden="true" size={15} />
            </button>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="empty-conversations">
            <strong>No chats yet</strong>
            <span>Start a conversation and it will appear here.</span>
          </div>
        )}
      </nav>
      <button className="secondary" onClick={onLogout} type="button">
        <LogOut aria-hidden="true" size={16} />
        <span>Logout</span>
      </button>
      {pendingDelete && (
        <div aria-modal="true" className="dialog-backdrop" role="dialog">
          <section className="dialog-panel">
            <div className="dialog-title-row">
              <h3>Delete conversation?</h3>
              <button
                aria-label="Close delete dialog"
                className="icon-button"
                onClick={() => setPendingDelete(null)}
                type="button"
              >
                <X aria-hidden="true" size={16} />
              </button>
            </div>
            <p>{pendingDelete.title}</p>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setPendingDelete(null)} type="button">
                Cancel
              </button>
              <button className="danger-button" disabled={deletingId === pendingDelete.id} onClick={confirmDelete} type="button">
                Delete
              </button>
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}

function formatConversationMeta(conversation: Conversation): string {
  const value = conversation.last_message_at ?? conversation.updated_at;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return conversation.status;
  }
  return `${conversation.status} · ${date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
  })}`;
}
