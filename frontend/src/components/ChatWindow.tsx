import { FormEvent, Fragment, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { Globe2, SendHorizontal } from 'lucide-react';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import type { RunStatus } from '../types/run';
import { CancelRunButton } from './CancelRunButton';
import { MessageBubble } from './MessageBubble';
import { RunStatusBadge } from './RunStatusBadge';
import { StreamingMessage } from './StreamingMessage';

interface ChatWindowProps {
  activeRunId: string | null;
  conversation: Conversation | null;
  loadingMessages: boolean;
  messages: Message[];
  onCancelRun: () => Promise<void>;
  onSend: (content: string, options?: { webSearchEnabled?: boolean }) => Promise<void>;
  runAnchorMessageId: string | null;
  runIsActive: boolean;
  runStatus: RunStatus | null;
  streamingText: string;
}

export function ChatWindow({
  activeRunId,
  conversation,
  loadingMessages,
  messages,
  onCancelRun,
  onSend,
  runAnchorMessageId,
  runIsActive,
  runStatus,
  streamingText,
}: ChatWindowProps) {
  const [content, setContent] = useState('');
  const [sending, setSending] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, streamingText]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = content.trim();
    if (!text || sending || runIsActive) {
      return;
    }
    setSending(true);
    try {
      await onSend(text, { webSearchEnabled });
      setContent('');
      setWebSearchEnabled(false);
    } finally {
      setSending(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
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
        {loadingMessages && <p className="muted">Loading messages...</p>}
        {messages.map((message) => (
          <Fragment key={message.id}>
            <MessageBubble message={message} />
            {message.id === runAnchorMessageId && (
              <StreamingMessage text={streamingText} />
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
          onKeyDown={handleComposerKeyDown}
          placeholder={runIsActive ? 'Agent is running...' : 'Ask the agent...'}
        />
        <div className="composer-actions">
          <button
            aria-pressed={webSearchEnabled}
            className={`composer-tool-button${webSearchEnabled ? ' active' : ''}`}
            disabled={sending || runIsActive}
            onClick={() => setWebSearchEnabled((enabled) => !enabled)}
            type="button"
          >
            <Globe2 aria-hidden="true" size={18} />
            <span>网页搜索</span>
          </button>
        </div>
        <button disabled={sending || runIsActive || !content.trim()} type="submit">
          <SendHorizontal aria-hidden="true" size={17} />
          <span>{sending || runIsActive ? 'Running' : 'Send'}</span>
        </button>
      </form>
    </div>
  );
}
