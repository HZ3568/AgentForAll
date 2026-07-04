import { FormEvent, useState } from 'react';
import type { AgentRunStatus, AgentToolCall } from '../types/agent';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import { MessageBubble } from './MessageBubble';
import { RunStatusBadge } from './RunStatusBadge';
import { ToolCallSummary } from './ToolCallSummary';

interface ChatWindowProps {
  conversation: Conversation | null;
  messages: Message[];
  onSend: (content: string) => Promise<void>;
  runStatus: AgentRunStatus | null;
  toolCalls: AgentToolCall[];
}

export function ChatWindow({ conversation, messages, onSend, runStatus, toolCalls }: ChatWindowProps) {
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
        <div className="chat-title-row">
          <h1>{conversation?.title ?? 'New Chat'}</h1>
          <RunStatusBadge status={sending ? 'running' : runStatus} />
        </div>
        <p>Non-streaming runtime is connected. Live events arrive in the next phase.</p>
        <ToolCallSummary toolCalls={toolCalls} />
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
          placeholder="Ask the agent..."
        />
        <button disabled={sending || !content.trim()} type="submit">
          {sending ? 'Running' : 'Send'}
        </button>
      </form>
    </div>
  );
}
