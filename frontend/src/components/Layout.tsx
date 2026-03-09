import { useEffect, useState } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { listBrands, deleteBrand } from '../api/brands';
import { listSessions, deleteSession, updateSession } from '../api/sessions';
import type { Brand, Session } from '../types';

export function Layout() {
  const { selectedBrandId, setSelectedBrandId } = useStore();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

  // Editing state for session rename
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const refreshBrands = () => listBrands().then(setBrands).catch(console.error);
  const refreshSessions = () => {
    if (selectedBrandId) {
      listSessions(selectedBrandId).then(setSessions).catch(console.error);
    } else {
      setSessions([]);
    }
  };

  useEffect(() => {
    refreshBrands();
  }, []);

  // Refresh brands when navigating back to dashboard (e.g. after creating a brand)
  useEffect(() => {
    if (location.pathname === '/') {
      refreshBrands();
    }
  }, [location.pathname]);

  // Refresh sessions when brand changes OR when route changes (new session created)
  useEffect(() => {
    refreshSessions();
  }, [selectedBrandId, location.pathname]);

  const AGENT_LABELS: Record<string, string> = {
    single_post: 'Single Post',
    carousel: 'Carousel',
    campaign: 'Campaign',
    sales_poster: 'Sales Poster',
    motion_graphics: 'Motion Graphics',
    product_video: 'Product Video',
  };

  // Highlight current session in sidebar
  const currentSessionId = location.pathname.startsWith('/chat/')
    ? location.pathname.split('/chat/')[1]
    : null;

  async function handleDeleteBrand(brandId: string, brandName: string) {
    if (!confirm(`Delete brand "${brandName}"? This will hide it from your list.`)) return;
    try {
      await deleteBrand(brandId);
      if (selectedBrandId === brandId) {
        setSelectedBrandId(null);
      }
      refreshBrands();
    } catch (err) {
      console.error('Failed to delete brand:', err);
    }
  }

  async function handleDeleteSession(sessionId: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm('Delete this session?')) return;
    try {
      await deleteSession(sessionId);
      if (currentSessionId === sessionId) {
        navigate('/');
      }
      refreshSessions();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }

  function startRename(sessionId: string, currentTitle: string, e: React.MouseEvent) {
    e.stopPropagation();
    setRenamingId(sessionId);
    setRenameValue(currentTitle);
  }

  async function submitRename(sessionId: string) {
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenamingId(null);
      return;
    }
    try {
      await updateSession(sessionId, { title: trimmed });
      refreshSessions();
    } catch (err) {
      console.error('Failed to rename session:', err);
    } finally {
      setRenamingId(null);
    }
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-64 min-h-0 flex-col border-r border-border bg-bg-card">
        <Link
          to="/"
          className="border-b border-border px-5 py-4 text-lg font-bold text-text-primary no-underline hover:text-accent"
        >
          Agent Factory
        </Link>

        {/* Brand Selector */}
        <div className="border-b border-border p-4">
          <label className="mb-1 block text-xs font-medium text-text-muted">Brand</label>
          <select
            value={selectedBrandId ?? ''}
            onChange={(e) => setSelectedBrandId(e.target.value || null)}
            className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="">Select a brand...</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <div className="mt-2 flex justify-center gap-3">
            <Link
              to="/brands/new"
              className="text-xs text-accent hover:text-accent-hover no-underline"
            >
              + New Brand
            </Link>
            {selectedBrandId && (
              <>
                <Link
                  to={`/brands/${selectedBrandId}/edit`}
                  className="text-xs text-text-muted hover:text-accent no-underline"
                >
                  Edit
                </Link>
                <button
                  onClick={() => {
                    const brand = brands.find((b) => b.id === selectedBrandId);
                    if (brand) handleDeleteBrand(brand.id, brand.name);
                  }}
                  className="text-xs text-text-muted hover:text-red-400"
                >
                  Delete
                </button>
              </>
            )}
          </div>
        </div>

        {/* Recent Sessions */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <h3 className="mb-2 text-xs font-medium text-text-muted">Recent Sessions</h3>
          {sessions.length === 0 ? (
            <p className="text-xs text-text-muted">
              {selectedBrandId ? 'No sessions yet' : 'Select a brand first'}
            </p>
          ) : (
            <ul className="space-y-1">
              {sessions.slice(0, 20).map((s) => (
                <li key={s.id} className="group">
                  {renamingId === s.id ? (
                    <div className="rounded-lg bg-bg-elevated px-3 py-2">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') submitRename(s.id);
                          if (e.key === 'Escape') setRenamingId(null);
                        }}
                        onBlur={() => submitRename(s.id)}
                        autoFocus
                        maxLength={255}
                        className="w-full rounded border border-border bg-bg-page px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
                      />
                    </div>
                  ) : (
                    <div className="relative">
                      <button
                        onClick={() => navigate(`/chat/${s.id}`)}
                        className={`w-full rounded-lg px-3 py-2 text-left text-xs transition-colors hover:bg-bg-elevated hover:text-text-primary ${
                          s.id === currentSessionId
                            ? 'bg-bg-elevated text-text-primary'
                            : 'text-text-muted'
                        }`}
                      >
                        <div className="font-medium text-text-primary">
                          {AGENT_LABELS[s.agent_type] || s.agent_type}
                        </div>
                        <div className="truncate pr-10">{s.title || 'Untitled'}</div>
                      </button>
                      {/* Session actions — visible on hover */}
                      <div className="absolute right-1 top-1 flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          onClick={(e) => startRename(s.id, s.title || '', e)}
                          title="Rename"
                          className="rounded p-1 text-text-muted hover:bg-bg-page hover:text-accent"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                            <path d="M13.49 3.51a3.73 3.73 0 0 0-5.27 0L2.64 9.09a.75.75 0 0 0-.2.39l-.67 3.35a.75.75 0 0 0 .88.88l3.35-.67a.75.75 0 0 0 .39-.2l5.58-5.58a3.73 3.73 0 0 0 0-5.27l-.48.49.48-.49ZM9.28 4.57a2.23 2.23 0 0 1 3.15 3.15l-5.58 5.58-2.2.44.44-2.2 5.58-5.58.61.61-.61-.61Z" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => handleDeleteSession(s.id, e)}
                          title="Delete"
                          className="rounded p-1 text-text-muted hover:bg-bg-page hover:text-red-400"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                            <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.31l.57 7.6A2 2 0 0 0 5.62 15h4.76a2 2 0 0 0 1.99-1.9l.57-7.6h.31a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm1.5 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 .75.75V4h-3v-.75ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.074l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.074l.275-5.5A.75.75 0 0 1 9.95 6Z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Outlet context={{ brands, refreshBrands }} />
      </main>
    </div>
  );
}
