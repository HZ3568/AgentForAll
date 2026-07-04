import { MessageContent } from './MessageBubble';

interface StreamingMessageProps {
  text: string;
}

export function StreamingMessage({ text }: StreamingMessageProps) {
  if (!text) {
    return null;
  }

  return (
    <article className="message assistant streaming">
      <div className="message-role">assistant</div>
      <MessageContent text={text} />
    </article>
  );
}
