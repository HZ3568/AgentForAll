import { useCallback, useEffect, useState } from 'react';
import { listMessages } from '../api/messages';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';

export function useConversationMessages(
  conversation: Conversation | null,
  onConversationChanged: () => void,
  onError: (message: string) => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const loadMessages = useCallback(async () => {
    if (!conversation) {
      setMessages([]);
      onConversationChanged();
      return [];
    }
    setLoading(true);
    try {
      const items = await listMessages(conversation.id);
      setMessages(items);
      onConversationChanged();
      return items;
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Load failed');
      return [];
    } finally {
      setLoading(false);
    }
  }, [conversation, onConversationChanged, onError]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  function appendMessageOnce(message: Message) {
    setMessages((items) => (items.some((item) => item.id === message.id) ? items : [...items, message]));
  }

  return {
    appendMessageOnce,
    loading,
    messages,
    setMessages,
  };
}
