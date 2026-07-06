import { FormEvent, Fragment, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { Bot, FileText, Globe2, Plus, Presentation, SendHorizontal, Table2, Telescope, Users } from 'lucide-react';
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
  onPreviewWorkspaceFile: (path: string) => void;
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
  onPreviewWorkspaceFile,
  onSend,
  runAnchorMessageId,
  runIsActive,
  runStatus,
  streamingText,
}: ChatWindowProps) {
  const [content, setContent] = useState('');
  const [composerMenuOpen, setComposerMenuOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const hasVisibleMessages = loadingMessages || messages.length > 0 || Boolean(streamingText);

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
      setComposerMenuOpen(false);
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
    <div className={hasVisibleMessages ? 'chat-window conversation-mode' : 'chat-window welcome-mode'}>
      {hasVisibleMessages && (
        <header className="chat-header">
          <div className="chat-title-row">
            <h1>{conversation?.title ?? '新对话'}</h1>
            <div className="run-actions">
              <RunStatusBadge status={sending ? 'queued' : runStatus} />
              <CancelRunButton runId={activeRunId} status={runStatus} onCancel={onCancelRun} />
            </div>
          </div>
        </header>
      )}
      <div className="message-list">
        {loadingMessages && <p className="muted">Loading messages...</p>}
        {messages.map((message) => (
          <Fragment key={message.id}>
            <MessageBubble message={message} onPreviewWorkspaceFile={onPreviewWorkspaceFile} />
            {message.id === runAnchorMessageId && (
              <StreamingMessage text={streamingText} />
            )}
          </Fragment>
        ))}
        {!hasVisibleMessages && (
          <section className="welcome-state" aria-label="欢迎">
            <div className="assistant-avatar large">
              <Bot aria-hidden="true" size={26} />
            </div>
            <h1>嗨，今天做点什么？</h1>
            <div className="welcome-chips" aria-label="快捷工具">
              <button className="welcome-chip" type="button">
                <Presentation aria-hidden="true" size={15} />
                <span>PPT</span>
              </button>
              <button className="welcome-chip" type="button">
                <Users aria-hidden="true" size={15} />
                <span>Agent 集群</span>
              </button>
              <button className="welcome-chip" type="button">
                <Telescope aria-hidden="true" size={15} />
                <span>深度研究</span>
              </button>
              <button className="welcome-chip" type="button">
                <FileText aria-hidden="true" size={15} />
                <span>文档</span>
              </button>
              <button className="welcome-chip" type="button">
                <Globe2 aria-hidden="true" size={15} />
                <span>网站</span>
              </button>
              <button className="welcome-chip" type="button">
                <Table2 aria-hidden="true" size={15} />
                <span>表格</span>
              </button>
            </div>
          </section>
        )}
        <div ref={messagesEndRef} />
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        {composerMenuOpen && (
          <div className="composer-popover">
            <button
              aria-pressed={webSearchEnabled}
              className={`composer-menu-item${webSearchEnabled ? ' active' : ''}`}
              disabled={sending || runIsActive}
              onClick={() => setWebSearchEnabled((enabled) => !enabled)}
              type="button"
            >
              <Globe2 aria-hidden="true" size={18} />
              <span>网页搜索</span>
            </button>
          </div>
        )}
        <button
          aria-expanded={composerMenuOpen}
          aria-label="添加附件和工具"
          className="composer-icon-button"
          disabled={sending || runIsActive}
          onClick={() => setComposerMenuOpen((open) => !open)}
          type="button"
        >
          <Plus aria-hidden="true" size={20} />
        </button>
        <textarea
          disabled={runIsActive}
          rows={1}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          onKeyDown={handleComposerKeyDown}
          placeholder={runIsActive ? 'Agent 正在运行...' : '输入 "/" 唤起插件和技能'}
        />
        <button
          aria-label="发送"
          className="composer-send-button"
          disabled={sending || runIsActive || !content.trim()}
          type="submit"
        >
          <SendHorizontal aria-hidden="true" size={17} />
          <span>{sending || runIsActive ? '运行中' : '发送'}</span>
        </button>
      </form>
    </div>
  );
}
