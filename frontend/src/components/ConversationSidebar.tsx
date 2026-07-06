import { AlarmClock, AppWindow, LogOut, MessageSquarePlus, MoreHorizontal, Plug, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import type { User } from '../types/auth';
import type { Conversation } from '../types/conversation';

interface ConversationSidebarProps {
  conversations: Conversation[];
  selectedId: string | null;
  user: User | null;
  onCreate: () => void;
  onDelete: (conversation: Conversation) => void | Promise<void>;
  deletingId: string | null;
  onSelect: (conversation: Conversation) => void;
  onLogout: () => void;
}

export function ConversationSidebar({
  conversations,
  selectedId,
  user,
  onCreate,
  onDelete,
  deletingId,
  onSelect,
  onLogout,
}: ConversationSidebarProps) {
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null);

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    await onDelete(pendingDelete);
    setPendingDelete(null);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">A</div>
        <button aria-label="折叠侧边栏" className="sidebar-mini-toggle" type="button">
          <AppWindow aria-hidden="true" size={17} />
        </button>
      </div>

      <button aria-label="新建会话" className="new-chat-button" onClick={onCreate} type="button">
        <MessageSquarePlus aria-hidden="true" size={17} />
        <span>新建会话</span>
        <kbd>Ctrl</kbd>
        <kbd>K</kbd>
      </button>

      <nav className="sidebar-nav" aria-label="功能">
        <button className="sidebar-nav-item" type="button">
          <Plug aria-hidden="true" size={17} />
          <span>插件</span>
        </button>
        <button className="sidebar-nav-item" type="button">
          <AlarmClock aria-hidden="true" size={17} />
          <span>定时任务</span>
        </button>
        <button className="sidebar-nav-item" type="button">
          <MoreHorizontal aria-hidden="true" size={17} />
          <span>更多</span>
        </button>
      </nav>

      <div className="sidebar-conversations">
        <span className="sidebar-section-label">对话</span>
        <nav className="conversation-list" aria-label="对话">
          {conversations.map((conversation) => (
            <div
              className={conversation.id === selectedId ? 'conversation active' : 'conversation'}
              key={conversation.id}
            >
              <button
                aria-current={conversation.id === selectedId ? 'page' : undefined}
                className="conversation-main"
                onClick={() => onSelect(conversation)}
                title={conversation.title}
                type="button"
              >
                <span>{conversation.title}</span>
              </button>
              <button
                aria-label={`删除 ${conversation.title}`}
                className="conversation-delete"
                disabled={deletingId === conversation.id}
                onClick={() => setPendingDelete(conversation)}
                title="删除对话"
                type="button"
              >
                <Trash2 aria-hidden="true" size={15} />
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <div className="empty-conversations">
              <strong>暂无对话</strong>
              <span>开始一次对话后会出现在这里。</span>
            </div>
          )}
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-account">
          <div className="account-avatar">{user?.username?.slice(0, 1).toUpperCase() ?? 'A'}</div>
          <div>
            <strong>{user?.username ?? '用户'}</strong>
            <p>{user ? user.email : '正在加载用户...'}</p>
          </div>
        </div>
        <button className="secondary" onClick={onLogout} type="button">
          <LogOut aria-hidden="true" size={16} />
          <span>退出登录</span>
        </button>
      </div>

      {pendingDelete && (
        <div aria-modal="true" className="dialog-backdrop" role="dialog">
          <section className="dialog-panel">
            <div className="dialog-title-row">
              <h3>删除这个对话？</h3>
              <button
                aria-label="关闭删除确认"
                className="icon-button"
                onClick={() => setPendingDelete(null)}
                type="button"
              >
                <X aria-hidden="true" size={16} />
              </button>
            </div>
            <p>{pendingDelete.title}</p>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setPendingDelete(null)} type="button">
                取消
              </button>
              <button
                className="danger-button"
                disabled={deletingId === pendingDelete.id}
                onClick={confirmDelete}
                type="button"
              >
                删除
              </button>
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}
