import { useEffect, useState } from 'react';
import { runAgentTurn } from '../api/agent';
import { createConversation, listConversations } from '../api/conversations';
import { listMessages } from '../api/messages';
import { ChatWindow } from '../components/ChatWindow';
import { ConversationSidebar } from '../components/ConversationSidebar';
import type { AgentRunStatus, AgentToolCall } from '../types/agent';
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
  const [runStatus, setRunStatus] = useState<AgentRunStatus | null>(null);
  const [toolCalls, setToolCalls] = useState<AgentToolCall[]>([]);
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
      setRunStatus(null);
      setToolCalls([]);
      return;
    }
    listMessages(selected.id)
      .then((items) => {
        setMessages(items);
        setRunStatus(null);
        setToolCalls([]);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, [selected?.id]);

  async function handleCreateConversation() {
    const conversation = await createConversation('New Chat');
    setConversations((items) => [conversation, ...items]);
    setSelected(conversation);
  }

  async function handleSend(content: string) {
    setError('');
    setRunStatus('running');
    setToolCalls([]);
    let target = selected;
    if (!selected) {
      target = await createConversation('New Chat');
      setConversations((items) => [target!, ...items]);
      setSelected(target);
      setMessages([]);
    }
    try {
      const response = await runAgentTurn(target!.id, content);
      setRunStatus(response.status);
      setToolCalls(response.tool_calls);
      setMessages((items) => [...items, response.user_message, ...response.assistant_messages]);
      await refreshConversations();
    } catch (err) {
      setRunStatus('failed');
      setError(err instanceof Error ? err.message : 'Agent run failed');
      throw err;
    }
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
        <ChatWindow
          conversation={selected}
          messages={messages}
          onSend={handleSend}
          runStatus={runStatus}
          toolCalls={toolCalls}
        />
      </section>
    </main>
  );
}
