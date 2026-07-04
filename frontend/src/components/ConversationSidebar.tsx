import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';

interface ConversationSidebarProps {
  conversations: Conversation[];
  selectedId: string | null;
  user: User | null;
  onCreate: () => void;
  onSelect: (conversation: Conversation) => void;
  onLogout: () => void;
}

export function ConversationSidebar({
  conversations,
  selectedId,
  user,
  onCreate,
  onSelect,
  onLogout,
}: ConversationSidebarProps) {
  return (
    <aside className="sidebar">
      <div>
        <h2>AgentForAll</h2>
        <p>{user ? user.email : 'Loading user...'}</p>
      </div>
      <button onClick={onCreate} type="button">
        New conversation
      </button>
      <nav className="conversation-list">
        {conversations.map((conversation) => (
          <button
            className={conversation.id === selectedId ? 'conversation active' : 'conversation'}
            key={conversation.id}
            onClick={() => onSelect(conversation)}
            type="button"
          >
            <span>{conversation.title}</span>
            <small>{conversation.status}</small>
          </button>
        ))}
        {conversations.length === 0 && <p className="muted">No conversations yet.</p>}
      </nav>
      <button className="secondary" onClick={onLogout} type="button">
        Logout
      </button>
    </aside>
  );
}
