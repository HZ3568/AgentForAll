import { useEffect, useState } from 'react';
import { createConversation, listConversations } from '../api/conversations';
import { listMessages } from '../api/messages';
import { cancelAgentRun, createAgentRun } from '../api/runs';
import { ChatWindow } from '../components/ChatWindow';
import { ConversationSidebar } from '../components/ConversationSidebar';
import { useRunEvents } from '../hooks/useRunEvents';
import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';
import type { Message } from '../types/message';
import type { RunEvent, RunStatus, ToolCallState } from '../types/run';

interface ChatPageProps {
  user: User | null;
  onLogout: () => void;
}

export function ChatPage({ user, onLogout }: ChatPageProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallState[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState('');

  const runIsActive = runStatus === 'queued' || runStatus === 'running' || runStatus === 'cancelling';

  async function refreshConversations() {
    const items = await listConversations();
    setConversations(items);
    if (!selected && items.length > 0) {
      setSelected(items[0]);
    }
  }

  useEffect(() => {
    refreshConversations().catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, []);

  useEffect(() => {
    if (!selected) {
      setMessages([]);
      resetRunState();
      return;
    }
    listMessages(selected.id)
      .then((items) => {
        setMessages(items);
        resetRunState();
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, [selected?.id]);

  useRunEvents(activeRunId, {
    enabled: Boolean(activeRunId),
    onEvent: handleRunEvent,
    onError: (err) => {
      setError(err.message);
      setRunStatus('failed');
      setActiveRunId(null);
    },
  });

  function resetRunState() {
    setActiveRunId(null);
    setRunStatus(null);
    setRunEvents([]);
    setToolCalls([]);
    setStreamingText('');
  }

  async function handleCreateConversation() {
    const conversation = await createConversation('New Chat');
    setConversations((items) => [conversation, ...items]);
    setSelected(conversation);
  }

  async function handleSend(content: string) {
    setError('');
    setRunStatus('queued');
    setRunEvents([]);
    setToolCalls([]);
    setStreamingText('');
    let target = selected;
    if (!selected) {
      target = await createConversation('New Chat');
      setConversations((items) => [target!, ...items]);
      setSelected(target);
      setMessages([]);
    }

    try {
      const response = await createAgentRun(target!.id, content);
      setRunStatus(response.status);
      setActiveRunId(response.run_id);
      appendMessageOnce(response.user_message);
      await refreshConversations();
    } catch (err) {
      setRunStatus('failed');
      setError(err instanceof Error ? err.message : 'Agent run failed');
      throw err;
    }
  }

  async function handleCancelRun() {
    if (!activeRunId) {
      return;
    }
    const response = await cancelAgentRun(activeRunId);
    setRunStatus(response.status);
    if (response.status === 'cancelled') {
      setActiveRunId(null);
      setStreamingText('');
    }
  }

  function handleRunEvent(event: RunEvent) {
    setRunEvents((items) =>
      items.some((item) => item.sequence_no === event.sequence_no) ? items : [...items, event],
    );
    const payload = asObject(event.event_json);

    if (event.event_type === 'run_queued') {
      setRunStatus('queued');
      return;
    }
    if (event.event_type === 'run_started') {
      setRunStatus('running');
      return;
    }
    if (event.event_type === 'run_cancel_requested') {
      setRunStatus('cancelling');
      return;
    }
    if (event.event_type === 'run_cancelled') {
      setRunStatus('cancelled');
      setActiveRunId(null);
      setStreamingText('');
      return;
    }
    if (event.event_type === 'run_failed') {
      setRunStatus('failed');
      setActiveRunId(null);
      setStreamingText('');
      setError(typeof payload.message === 'string' ? payload.message : 'Agent run failed');
      return;
    }
    if (event.event_type === 'run_finished') {
      setRunStatus('succeeded');
      setActiveRunId(null);
      setStreamingText('');
      refreshConversations().catch(() => undefined);
      return;
    }
    if (event.event_type === 'assistant_delta') {
      const delta = typeof payload.delta === 'string' ? payload.delta : typeof payload.text === 'string' ? payload.text : '';
      if (delta) {
        setStreamingText((text) => (text.endsWith(delta) ? text : `${text}${delta}`));
      }
      return;
    }
    if (event.event_type === 'assistant_message_created') {
      const message = buildMessageFromEvent(event, payload, 'assistant');
      if (message) {
        appendMessageOnce(message);
      }
      setStreamingText('');
      return;
    }
    if (
      event.event_type === 'tool_call_started' ||
      event.event_type === 'tool_call_finished' ||
      event.event_type === 'tool_call_failed'
    ) {
      upsertToolCall(payload);
    }
  }

  function buildMessageFromEvent(event: RunEvent, payload: Record<string, unknown>, fallbackRole: Message['role']): Message | null {
    const messageId = typeof payload.message_id === 'string' ? payload.message_id : null;
    const contentText = typeof payload.content_text === 'string' ? payload.content_text : '';
    const role = payload.role === 'user' || payload.role === 'assistant' ? payload.role : fallbackRole;
    if (!messageId || !selected || !user) {
      return null;
    }
    return {
      id: messageId,
      conversation_id: selected.id,
      user_id: user.id,
      role,
      content_json: { type: 'text', text: contentText },
      content_text: contentText,
      token_count: null,
      sequence_no: nextMessageSequenceNo(),
      created_at: event.created_at,
    };
  }

  function nextMessageSequenceNo() {
    return Math.max(0, ...messages.map((message) => message.sequence_no)) + 1;
  }

  function appendMessageOnce(message: Message) {
    setMessages((items) => (items.some((item) => item.id === message.id) ? items : [...items, message]));
  }

  function upsertToolCall(payload: Record<string, unknown>) {
    const id = typeof payload.tool_call_id === 'string' ? payload.tool_call_id : null;
    const toolName = typeof payload.tool_name === 'string' ? payload.tool_name : 'tool';
    const status = typeof payload.status === 'string' ? payload.status : 'running';
    if (!id) {
      return;
    }
    setToolCalls((items) => {
      const existing = items.find((item) => item.id === id);
      if (!existing) {
        return [...items, { id, tool_name: toolName, status }];
      }
      return items.map((item) => (item.id === id ? { ...item, tool_name: toolName, status } : item));
    });
  }

  function asObject(value: unknown): Record<string, unknown> {
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
  }

  return (
    <main className="chat-layout">
      <ConversationSidebar
        conversations={conversations}
        selectedId={selected?.id ?? null}
        user={user}
        onCreate={handleCreateConversation}
        onSelect={setSelected}
        onLogout={onLogout}
      />
      <section className="chat-main">
        {error && <div className="error">{error}</div>}
        <ChatWindow
          activeRunId={activeRunId}
          conversation={selected}
          messages={messages}
          onCancelRun={handleCancelRun}
          onSend={handleSend}
          runEvents={runEvents}
          runIsActive={runIsActive}
          runStatus={runStatus}
          streamingText={streamingText}
          toolCalls={toolCalls}
        />
      </section>
    </main>
  );
}
