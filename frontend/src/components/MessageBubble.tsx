import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../types/message';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <article className={`message ${message.role}`}>
      <div className="message-role">{message.role}</div>
      <MessageContent text={message.content_text} />
    </article>
  );
}

interface MessageContentProps {
  text: string;
}

export function MessageContent({ text }: MessageContentProps) {
  return (
    <div className="message-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
