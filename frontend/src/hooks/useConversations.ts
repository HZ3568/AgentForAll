import { useCallback, useEffect, useState } from 'react';
import {
  createConversation,
  deleteConversation,
  listConversations,
  updateConversationTitle,
} from '../api/conversations';
import type { Conversation } from '../types/conversation';

export function useConversations(onError: (message: string) => void) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);

  const refreshConversations = useCallback(async () => {
    const items = await listConversations();
    setConversations(items);
    setSelected((current) => {
      if (current && items.some((item) => item.id === current.id)) {
        return items.find((item) => item.id === current.id) ?? current;
      }
      return items[0] ?? null;
    });
    return items;
  }, []);

  useEffect(() => {
    refreshConversations()
      .catch((err) => onError(err instanceof Error ? err.message : 'Load failed'))
      .finally(() => setLoading(false));
  }, [onError, refreshConversations]);

  async function createNewConversation(): Promise<Conversation> {
    const conversation = await createConversation('New Chat');
    setConversations((items) => [conversation, ...items]);
    setSelected(conversation);
    return conversation;
  }

  async function removeConversation(conversation: Conversation): Promise<void> {
    setDeletingConversationId(conversation.id);
    try {
      await deleteConversation(conversation.id);
      setConversations((items) => {
        const remaining = items.filter((item) => item.id !== conversation.id);
        setSelected((current) => (current?.id === conversation.id ? remaining[0] ?? null : current));
        return remaining;
      });
    } finally {
      setDeletingConversationId(null);
    }
  }

  async function renameConversation(conversation: Conversation, title: string): Promise<void> {
    const updated = await updateConversationTitle(conversation.id, title);
    setSelected((current) => (current?.id === updated.id ? updated : current));
    setConversations((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  }

  return {
    conversations,
    createNewConversation,
    deletingConversationId,
    loading,
    refreshConversations,
    removeConversation,
    renameConversation,
    selected,
    setSelected,
  };
}
