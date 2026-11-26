import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Plus,
  MagnifyingGlass,
  PencilSimple,
  Archive,
  ArrowCounterClockwise,
  Trash,
  ChatCircleText,
  Clock,
  X,
  Check,
  Sparkle
} from '../icons';
import { aiSessionService, AISession } from '../../services/aiSessionService';
import toast from 'react-hot-toast';
import './SessionSidebar.css';

interface SessionSidebarProps {
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  isOpen: boolean;
  onClose: () => void;
  onOpenSearchHistory?: () => void;
}

interface GroupedSessions {
  today: AISession[];
  yesterday: AISession[];
  previous7Days: AISession[];
  previous30Days: AISession[];
  older: AISession[];
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  activeSessionId,
  onSelectSession,
  onNewSession,
  isOpen,
  onClose,
  onOpenSearchHistory,
}) => {
  const [sessions, setSessions] = useState<AISession[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'active' | 'archived'>('active');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await aiSessionService.listSessions(activeTab, undefined, searchQuery || undefined, 50);
      setSessions(res.items || []);
    } catch (err) {
      console.error('Failed loading sessions', err);
    } finally {
      setLoading(false);
    }
  }, [activeTab, searchQuery]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Group sessions chronologically into standard ChatGPT-style time buckets
  const groupedSessions = useMemo<GroupedSessions>(() => {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfYesterday = startOfToday - 86400000;
    const sevenDaysAgo = startOfToday - 7 * 86400000;
    const thirtyDaysAgo = startOfToday - 30 * 86400000;

    const groups: GroupedSessions = {
      today: [],
      yesterday: [],
      previous7Days: [],
      previous30Days: [],
      older: [],
    };

    sessions.forEach((s) => {
      const ts = new Date(s.last_message_at || s.created_at).getTime();
      if (ts >= startOfToday) {
        groups.today.push(s);
      } else if (ts >= startOfYesterday) {
        groups.yesterday.push(s);
      } else if (ts >= sevenDaysAgo) {
        groups.previous7Days.push(s);
      } else if (ts >= thirtyDaysAgo) {
        groups.previous30Days.push(s);
      } else {
        groups.older.push(s);
      }
    });

    return groups;
  }, [sessions]);

  const handleStartRename = (s: AISession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditTitle(s.title);
  };

  const handleSaveRename = async (sessionId: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!editTitle.trim()) return;

    try {
      await aiSessionService.updateSession(sessionId, { title: editTitle.trim() });
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: editTitle.trim() } : s))
      );
      setEditingId(null);
      toast.success('Conversation renamed');
    } catch {
      toast.error('Failed to rename conversation');
    }
  };

  const handleArchive = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await aiSessionService.archiveSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      toast.success('Conversation archived');
    } catch {
      toast.error('Failed to archive conversation');
    }
  };

  const handleRestore = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await aiSessionService.restoreSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      toast.success('Conversation restored');
    } catch {
      toast.error('Failed to restore conversation');
    }
  };

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await aiSessionService.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setConfirmDeleteId(null);
      toast.success('Conversation deleted');
      if (activeSessionId === sessionId) {
        onNewSession();
      }
    } catch {
      toast.error('Failed to delete conversation');
    }
  };

  const renderSessionItem = (s: AISession) => {
    const isActive = activeSessionId === s.id;
    const isEditing = editingId === s.id;
    const isConfirmingDelete = confirmDeleteId === s.id;

    if (isEditing) {
      return (
        <form
          key={s.id}
          className="ai-session-item editing"
          onSubmit={(e) => handleSaveRename(s.id, e)}
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="text"
            className="ai-session-rename-input"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            autoFocus
            maxLength={100}
          />
          <button type="submit" className="ai-session-action-btn" title="Save">
            <Check size={14} weight="bold" />
          </button>
          <button
            type="button"
            className="ai-session-action-btn"
            title="Cancel"
            onClick={() => setEditingId(null)}
          >
            <X size={14} />
          </button>
        </form>
      );
    }

    return (
      <div
        key={s.id}
        className={`ai-session-item ${isActive ? 'active' : ''}`}
        onClick={() => onSelectSession(s.id)}
      >
        <ChatCircleText size={16} className="ai-session-icon" weight={isActive ? 'fill' : 'regular'} />
        <span className="ai-session-title" title={s.title}>
          {s.title || 'Untitled conversation'}
        </span>

        {isConfirmingDelete ? (
          <div className="ai-session-delete-confirm" onClick={(e) => e.stopPropagation()}>
            <span className="confirm-label">Delete?</span>
            <button
              className="confirm-yes-btn"
              onClick={(e) => handleDelete(s.id, e)}
              title="Confirm Delete"
            >
              <Check size={13} weight="bold" />
            </button>
            <button
              className="confirm-no-btn"
              onClick={() => setConfirmDeleteId(null)}
              title="Cancel"
            >
              <X size={13} />
            </button>
          </div>
        ) : (
          <div className="ai-session-actions">
            <button
              className="ai-session-action-btn"
              title="Rename"
              onClick={(e) => handleStartRename(s, e)}
            >
              <PencilSimple size={14} />
            </button>

            {activeTab === 'active' ? (
              <button
                className="ai-session-action-btn"
                title="Archive"
                onClick={(e) => handleArchive(s.id, e)}
              >
                <Archive size={14} />
              </button>
            ) : (
              <button
                className="ai-session-action-btn"
                title="Restore"
                onClick={(e) => handleRestore(s.id, e)}
              >
                <ArrowCounterClockwise size={14} />
              </button>
            )}

            <button
              className="ai-session-action-btn delete"
              title="Delete"
              onClick={(e) => {
                e.stopPropagation();
                setConfirmDeleteId(s.id);
              }}
            >
              <Trash size={14} />
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderGroup = (label: string, items: AISession[]) => {
    if (!items || items.length === 0) return null;
    return (
      <div className="ai-session-group" key={label}>
        <div className="ai-session-group-label">{label}</div>
        <div className="ai-session-group-items">{items.map(renderSessionItem)}</div>
      </div>
    );
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && <div className="ai-sidebar-backdrop mobile-only" onClick={onClose} />}

      <aside className={`ai-session-sidebar ${isOpen ? 'open' : 'collapsed'}`}>
        <div className="ai-sidebar-header">
          <button className="ai-new-chat-btn" onClick={onNewSession}>
            <Plus size={18} weight="bold" />
            <span>New conversation</span>
          </button>
          <button className="ai-sidebar-close-btn mobile-only" onClick={onClose} title="Close Sidebar">
            <X size={18} />
          </button>
        </div>

        {/* Search Past Conversations */}
        <div className="ai-sidebar-search">
          <MagnifyingGlass size={15} className="search-icon" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>
              <X size={12} />
            </button>
          )}
        </div>

        {/* Active vs Archived Tab Filter */}
        <div className="ai-sidebar-tabs">
          <button
            className={`ai-tab-btn ${activeTab === 'active' ? 'active' : ''}`}
            onClick={() => setActiveTab('active')}
          >
            Chats
          </button>
          <button
            className={`ai-tab-btn ${activeTab === 'archived' ? 'active' : ''}`}
            onClick={() => setActiveTab('archived')}
          >
            Archived
          </button>
        </div>

        {/* Sessions List */}
        <div className="ai-sidebar-sessions-list custom-scrollbar">
          {loading && sessions.length === 0 ? (
            <div className="ai-sidebar-loading">
              <Sparkle size={20} className="spin-icon" />
              <span>Loading conversations...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="ai-sidebar-empty">
              <ChatCircleText size={32} className="empty-icon" />
              <p>No {activeTab} conversations found</p>
              {activeTab === 'active' && (
                <button className="ai-sidebar-start-btn" onClick={onNewSession}>
                  Start Styling
                </button>
              )}
            </div>
          ) : (
            <>
              {renderGroup('Today', groupedSessions.today)}
              {renderGroup('Yesterday', groupedSessions.yesterday)}
              {renderGroup('Previous 7 Days', groupedSessions.previous7Days)}
              {renderGroup('Previous 30 Days', groupedSessions.previous30Days)}
              {renderGroup('Older', groupedSessions.older)}
            </>
          )}
        </div>

        {/* Footer with Search History Shortcut */}
        {onOpenSearchHistory && (
          <div className="ai-sidebar-footer">
            <button className="ai-search-history-trigger" onClick={onOpenSearchHistory}>
              <Clock size={16} />
              <span>Search History & Provenance</span>
            </button>
          </div>
        )}
      </aside>
    </>
  );
};
