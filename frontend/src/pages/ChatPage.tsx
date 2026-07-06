import { useCallback, useEffect, useRef, useState } from 'react';
import { getMemoryIndex, listWorkspaceFiles } from '../api/conversations';
import { createAgentRun } from '../api/runs';
import { AgentWorkbench } from '../components/AgentWorkbench';
import { ChatWindow } from '../components/ChatWindow';
import { ConversationSidebar } from '../components/ConversationSidebar';
import { useActiveRun } from '../hooks/useActiveRun';
import { useConversationMessages } from '../hooks/useConversationMessages';
import { useConversations } from '../hooks/useConversations';
import type { User } from '../types/auth';
import type { Conversation, WorkspaceFile } from '../types/conversation';
import {
  generateConversationTitle,
  shouldAutoTitleConversation,
} from '../utils/conversationTitle';

interface ChatPageProps {
  user: User | null;
  onLogout: () => void;
}

export function ChatPage({ user, onLogout }: ChatPageProps) {
  const [error, setError] = useState('');
  const [memoryIndex, setMemoryIndex] = useState<string | null>(null);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const recoveredConversationId = useRef<string | null>(null);

  const showError = useCallback((message: string) => {
    setError(message);
  }, []);

  const {
    conversations,
    createNewConversation,
    deletingConversationId,
    loading: conversationsLoading,
    refreshConversations,
    removeConversation,
    renameConversation,
    selected,
    setSelected,
  } = useConversations(showError);

  const onConversationChanged = useCallback(() => {
    recoveredConversationId.current = null;
  }, []);

  const {
    appendMessageOnce,
    loading: messagesLoading,
    messages,
    setMessages,
  } = useConversationMessages(selected, onConversationChanged, showError);

  const {
    activeRunId,
    attachCreatedRun,
    cancelActiveRun,
    recoverActiveRun,
    resetRunState,
    runAnchorMessageId,
    runError,
    runEvents,
    runIsActive,
    runStatus,
    streamingText,
    toolCalls,
  } = useActiveRun({
    appendMessageOnce,
    conversation: selected,
    messages,
    onError: showError,
    onRefreshConversations: refreshConversations,
    user,
  });

  useEffect(() => {
    resetRunState();
    setMemoryIndex(null);
    setWorkspaceFiles([]);
  }, [resetRunState, selected?.id]);

  useEffect(() => {
    if (runError) {
      showError(runError);
    }
  }, [runError, showError]);

  useEffect(() => {
    if (!selected || messagesLoading) {
      return;
    }
    if (messages.some((message) => message.conversation_id !== selected.id)) {
      return;
    }
    if (recoveredConversationId.current === selected.id) {
      return;
    }
    recoveredConversationId.current = selected.id;
    recoverActiveRun(messages).catch((err) => showError(err instanceof Error ? err.message : 'Run recovery failed'));
  }, [messages, messagesLoading, recoverActiveRun, selected, showError]);

  useEffect(() => {
    if (!selected) {
      setMemoryIndex(null);
      setWorkspaceFiles([]);
      return;
    }
    let cancelled = false;
    Promise.all([listWorkspaceFiles(selected.id), getMemoryIndex(selected.id)])
      .then(([files, memory]) => {
        if (!cancelled) {
          setWorkspaceFiles(files);
          setMemoryIndex(memory);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMemoryIndex(null);
          setWorkspaceFiles([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selected?.id, runStatus]);

  async function handleCreateConversation() {
    setError('');
    const conversation = await createNewConversation();
    setSelected(conversation);
    setMessages([]);
    resetRunState();
  }

  async function handleDeleteConversation(conversation: Conversation) {
    setError('');
    try {
      if (conversation.id === selected?.id && activeRunId && runIsActive) {
        await cancelActiveRun().catch(() => undefined);
      }
      await removeConversation(conversation);
      if (conversation.id === selected?.id) {
        setMessages([]);
        resetRunState();
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  async function handleSend(content: string, options?: { webSearchEnabled?: boolean }) {
    setError('');
    let target = selected;
    if (!target) {
      target = await createNewConversation();
      setSelected(target);
      setMessages([]);
    }

    try {
      const response = await createAgentRun(target.id, content, options);
      attachCreatedRun(response);
      appendMessageOnce(response.user_message);
      if (shouldAutoTitleConversation(target.title, messages.length)) {
        await renameConversationFromMessage(target, content);
      }
      await refreshConversations();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Agent run failed');
      throw err;
    }
  }

  async function renameConversationFromMessage(conversation: Conversation, content: string) {
    const title = generateConversationTitle(content);
    if (!title || title === conversation.title) {
      return;
    }
    try {
      await renameConversation(conversation, title);
    } catch {
      // Conversation titles are a convenience; a failed rename must not fail the run.
    }
  }

  return (
    <main className="chat-layout">
      <ConversationSidebar
        conversations={conversations}
        selectedId={selected?.id ?? null}
        user={user}
        onCreate={handleCreateConversation}
        onDelete={handleDeleteConversation}
        deletingId={deletingConversationId}
        onSelect={setSelected}
        onLogout={onLogout}
      />
      <section className="chat-main">
        {error && (
          <div className="error app-error">
            <span>{error}</span>
            <button className="icon-button" onClick={() => setError('')} type="button">
              Dismiss
            </button>
          </div>
        )}
        {conversationsLoading && <div className="loading-strip">Loading conversations...</div>}
        <div className="chat-workspace">
          <ChatWindow
            activeRunId={activeRunId}
            conversation={selected}
            loadingMessages={messagesLoading}
            messages={messages}
            onCancelRun={cancelActiveRun}
            onSend={handleSend}
            runAnchorMessageId={runAnchorMessageId}
            runIsActive={runIsActive}
            runStatus={runStatus}
            streamingText={streamingText}
          />
          <AgentWorkbench
            activeRunId={activeRunId}
            memoryIndex={memoryIndex}
            runEvents={runEvents}
            runStatus={runStatus}
            toolCalls={toolCalls}
            workspaceFiles={workspaceFiles}
          />
        </div>
      </section>
    </main>
  );
}
