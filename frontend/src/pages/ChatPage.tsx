import { useEffect, useState } from 'react';
import { createConversation, listConversations } from '../api/conversations';
import { listMessages, sendMessage } from '../api/messages';
import { ChatWindow } from '../components/ChatWindow';
import { ConversationSidebar } from '../components/ConversationSidebar';
import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';

interface ChatPageProps {
  user: User | null;
  onLogout: () => void;
}

export function ChatPage({ user, onLogout }: ChatPageProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');

  async function refreshConversations() {
    const items = await listConversations();
    setConversations(items);
    if (!selected && items.length > 0) {
      setSelected(items[0]);
    }
  }

  useEffect(() => {
    refreshConversations().catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, []);

  useEffect(() => {
    if (!selected) {
      setMessages([]);
      return;
    }
    listMessages(selected.id)
      .then(setMessages)
      .catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, [selected?.id]);

  async function handleCreateConversation() {
    const conversation = await createConversation('New Chat');
    setConversations((items) => [conversation, ...items]);
    setSelected(conversation);
  }

  async function handleSend(content: string) {
    if (!selected) {
      const conversation = await createConversation('New Chat');
      setConversations((items) => [conversation, ...items]);
      setSelected(conversation);
      const message = await sendMessage(conversation.id, content);
      setMessages([message]);
      return;
    }
    const message = await sendMessage(selected.id, content);
    setMessages((items) => [...items, message]);
    await refreshConversations();
  }

  return (
    <main className="chat-layout">
      <ConversationSidebar
        conversations={conversations}
        selectedId={selected?.id ?? null}
        user={user}
        onCreate={handleCreateConversation}
        onSelect={setSelected}
        onLogout={onLogout}
      />
      <section className="chat-main">
        {error && <div className="error">{error}</div>}
        <ChatWindow conversation={selected} messages={messages} onSend={handleSend} />
      </section>
    </main>
  );
}
