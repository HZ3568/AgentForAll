import { FormEvent, useState } from 'react';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import { MessageBubble } from './MessageBubble';

interface ChatWindowProps {
  conversation: Conversation | null;
  messages: Message[];
  onSend: (content: string) => Promise<void>;
}

export function ChatWindow({ conversation, messages, onSend }: ChatWindowProps) {
  const [content, setContent] = useState('');
  const [sending, setSending] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = content.trim();
    if (!text || sending) {
      return;
    }
    setSending(true);
    try {
      await onSend(text);
      setContent('');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-window">
      <header className="chat-header">
        <h1>{conversation?.title ?? 'New Chat'}</h1>
        <p>Agent runtime will be connected in the next phase.</p>
      </header>
      <div className="message-list">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {messages.length === 0 && <p className="muted">Send a message to start the conversation.</p>}
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Type a user message..."
        />
        <button disabled={sending || !content.trim()} type="submit">
          Send
        </button>
      </form>
    </div>
  );
}
