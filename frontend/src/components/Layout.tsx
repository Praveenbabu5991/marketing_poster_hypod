import { useEffect, useState } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { listBrands } from '../api/brands';
import { listSessions } from '../api/sessions';
import type { Brand, Session } from '../types';

export function Layout() {
  const { selectedBrandId, setSelectedBrandId } = useStore();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    listBrands().then(setBrands).catch(console.error);
  }, []);

  // Refresh brands when navigating back to dashboard (e.g. after creating a brand)
  useEffect(() => {
    if (location.pathname === '/') {
      listBrands().then(setBrands).catch(console.error);
    }
  }, [location.pathname]);

  // Refresh sessions when brand changes OR when route changes (new session created)
  useEffect(() => {
    if (selectedBrandId) {
      listSessions(selectedBrandId).then(setSessions).catch(console.error);
    } else {
      setSessions([]);
    }
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
              <Link
                to={`/brands/${selectedBrandId}/edit`}
                className="text-xs text-text-muted hover:text-accent no-underline"
              >
                Edit Brand
              </Link>
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
                <li key={s.id}>
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
                    <div className="truncate">{s.title || 'Untitled'}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Outlet context={{ brands, refreshBrands: () => listBrands().then(setBrands) }} />
      </main>
    </div>
  );
}
