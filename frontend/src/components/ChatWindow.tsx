import { FormEvent, Fragment, useEffect, useRef, useState } from 'react';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import type { RunEvent, RunStatus, ToolCallState } from '../types/run';
import { CancelRunButton } from './CancelRunButton';
import { MessageBubble } from './MessageBubble';
import { RunEventTimeline } from './RunEventTimeline';
import { RunStatusBadge } from './RunStatusBadge';
import { StreamingMessage } from './StreamingMessage';
import { ToolCallTimeline } from './ToolCallTimeline';

interface ChatWindowProps {
  activeRunId: string | null;
  conversation: Conversation | null;
  messages: Message[];
  onCancelRun: () => Promise<void>;
  onSend: (content: string) => Promise<void>;
  runAnchorMessageId: string | null;
  runEvents: RunEvent[];
  runIsActive: boolean;
  runStatus: RunStatus | null;
  streamingText: string;
  toolCalls: ToolCallState[];
}

export function ChatWindow({
  activeRunId,
  conversation,
  messages,
  onCancelRun,
  onSend,
  runAnchorMessageId,
  runEvents,
  runIsActive,
  runStatus,
  streamingText,
  toolCalls,
}: ChatWindowProps) {
  const [content, setContent] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, runEvents.length, streamingText]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = content.trim();
    if (!text || sending || runIsActive) {
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
          <div className="run-actions">
            <RunStatusBadge status={sending ? 'queued' : runStatus} />
            <CancelRunButton runId={activeRunId} status={runStatus} onCancel={onCancelRun} />
          </div>
        </div>
      </header>
      <div className="message-list">
        {messages.map((message) => (
          <Fragment key={message.id}>
            <MessageBubble message={message} />
            {message.id === runAnchorMessageId && (
              <>
                <RunEventTimeline events={runEvents} status={runStatus} />
                <ToolCallTimeline toolCalls={toolCalls} />
                <StreamingMessage text={streamingText} />
              </>
            )}
          </Fragment>
        ))}
        {messages.length === 0 && !streamingText && <p className="muted">Send a message to start the conversation.</p>}
        <div ref={messagesEndRef} />
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          disabled={runIsActive}
          rows={1}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder={runIsActive ? 'Agent is running...' : 'Ask the agent...'}
        />
        <button disabled={sending || runIsActive || !content.trim()} type="submit">
          {sending || runIsActive ? 'Running' : 'Send'}
        </button>
      </form>
    </div>
  );
}
