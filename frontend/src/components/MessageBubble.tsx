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
  const parts = splitFencedCode(text);
  return (
    <div className="message-content">
      {parts.map((part, index) =>
        part.type === 'code' ? (
          <pre key={`${part.type}-${index}`}>
            <code>{part.content}</code>
          </pre>
        ) : (
          <p key={`${part.type}-${index}`}>{part.content}</p>
        ),
      )}
    </div>
  );
}

type MessagePart = { type: 'text' | 'code'; content: string };

function splitFencedCode(text: string): MessagePart[] {
  const parts: MessagePart[] = [];
  const pattern = /```[a-zA-Z0-9_-]*\n?([\s\S]*?)```/g;
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    const before = text.slice(cursor, match.index);
    if (before.trim()) {
      parts.push({ type: 'text', content: before });
    }
    parts.push({ type: 'code', content: match[1].trimEnd() });
    cursor = match.index + match[0].length;
  }
  const rest = text.slice(cursor);
  if (rest.trim() || parts.length === 0) {
    parts.push({ type: 'text', content: rest });
  }
  return parts;
}
