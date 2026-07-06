import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot } from 'lucide-react';
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from 'react';
import type { Message } from '../types/message';

interface MessageBubbleProps {
  message: Message;
  onPreviewWorkspaceFile?: (path: string) => void;
}

const WORKSPACE_LINK_PREFIXES = ['uploads/', 'artifacts/', 'traces/'];

export function MessageBubble({ message, onPreviewWorkspaceFile }: MessageBubbleProps) {
  const isAssistant = message.role === 'assistant';
  return (
    <article className={`message ${message.role}`}>
      {isAssistant && (
        <div className="assistant-avatar">
          <Bot aria-hidden="true" size={17} />
        </div>
      )}
      <div className="message-body">
        <div className="message-role">{message.role}</div>
        <MessageContent text={message.content_text} onPreviewWorkspaceFile={onPreviewWorkspaceFile} />
      </div>
    </article>
  );
}

interface MessageContentProps {
  onPreviewWorkspaceFile?: (path: string) => void;
  text: string;
}

export function MessageContent({ onPreviewWorkspaceFile, text }: MessageContentProps) {
  return (
    <div className="message-content">
      <ReactMarkdown
        components={{
          a: ({ children, href, ...props }) => (
            <MarkdownLink href={href} onPreviewWorkspaceFile={onPreviewWorkspaceFile} {...props}>
              {children}
            </MarkdownLink>
          ),
        }}
        remarkPlugins={[remarkGfm]}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

interface MarkdownLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
  href?: string;
  onPreviewWorkspaceFile?: (path: string) => void;
}

function MarkdownLink({ children, href, onPreviewWorkspaceFile, ...props }: MarkdownLinkProps) {
  const workspacePath = href ? getWorkspacePreviewPath(href) : null;

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (!workspacePath || !onPreviewWorkspaceFile) {
      return;
    }
    event.preventDefault();
    onPreviewWorkspaceFile(workspacePath);
  }

  return (
    <a
      {...props}
      href={href}
      onClick={handleClick}
      rel={workspacePath ? undefined : 'noreferrer'}
      target={workspacePath ? undefined : '_blank'}
    >
      {children}
    </a>
  );
}

function getWorkspacePreviewPath(href: string): string | null {
  const normalized = href.replace(/^\.?\//, '');
  if (normalized.includes('://') || normalized.startsWith('#') || normalized.includes('..')) {
    return null;
  }
  return WORKSPACE_LINK_PREFIXES.some((prefix) => normalized.startsWith(prefix)) ? normalized : null;
}
