import type { Message } from '../types/message';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <article className={`message ${message.role}`}>
      <div className="message-role">{message.role}</div>
      <p>{message.content_text}</p>
    </article>
  );
}
