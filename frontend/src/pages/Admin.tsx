import { useEffect, useState } from 'react';
import {
  getOverview,
  listUsers,
  getAlerts,
  adminTopUp,
  type Overview,
  type AdminUser,
  type Alert,
} from '../api/admin';

type Tab = 'overview' | 'users' | 'alerts';

export function Admin() {
  const [tab, setTab] = useState<Tab>('overview');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [atRiskOnly, setAtRiskOnly] = useState(false);
  const [planFilter, setPlanFilter] = useState<string>('');

  useEffect(() => {
    setLoading(true);
    setError(null);
    const load = async () => {
      try {
        if (tab === 'overview') {
          setOverview(await getOverview(days));
        } else if (tab === 'users') {
          const r = await listUsers({
            days,
            at_risk: atRiskOnly,
            plan: planFilter || undefined,
          });
          setUsers(r.items);
        } else if (tab === 'alerts') {
          const r = await getAlerts(days);
          setAlerts(r.alerts);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [tab, days, atRiskOnly, planFilter]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Admin Dashboard</h1>
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Window</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-border bg-bg-card px-3 py-1 text-sm text-text-primary"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-1 border-b border-border">
        {(['overview', 'users', 'alerts'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? 'border-b-2 border-accent text-text-primary'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-text-muted">Loading…</div>}

      {/* Overview Tab */}
      {tab === 'overview' && overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <MetricCard label="Revenue" value={`₹${overview.revenue_inr.toLocaleString()}`} />
            <MetricCard label="API Cost" value={`₹${overview.cost_inr.toLocaleString()}`} />
            <MetricCard
              label="Margin"
              value={`₹${overview.margin_inr.toLocaleString()}`}
              sub={`${overview.margin_pct}%`}
              tone={overview.margin_pct >= 40 ? 'good' : overview.margin_pct >= 20 ? 'warn' : 'bad'}
            />
            <MetricCard
              label="Loss-makers"
              value={String(overview.loss_makers_count)}
              sub="cost > plan"
              tone={overview.loss_makers_count === 0 ? 'good' : 'warn'}
            />
          </div>

          <div className="rounded-lg border border-border bg-bg-card p-4">
            <h3 className="mb-3 text-sm font-semibold text-text-primary">Users by Plan</h3>
            <div className="flex flex-wrap gap-4">
              {Object.entries(overview.user_count_by_plan).map(([plan, count]) => (
                <div key={plan} className="rounded-lg bg-bg-elevated px-3 py-2">
                  <div className="text-xs text-text-muted">{plan}</div>
                  <div className="text-lg font-semibold text-text-primary">{count}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-bg-card p-4">
            <h3 className="mb-3 text-sm font-semibold text-text-primary">
              Top Models by Cost
            </h3>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-text-muted">
                <tr>
                  <th className="py-2">Model</th>
                  <th className="py-2">Calls</th>
                  <th className="py-2">Cost (₹)</th>
                </tr>
              </thead>
              <tbody>
                {overview.top_models.map((m) => (
                  <tr key={m.model} className="border-t border-border">
                    <td className="py-2 font-mono text-xs">{m.model}</td>
                    <td className="py-2">{m.calls}</td>
                    <td className="py-2">₹{m.cost_inr.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={atRiskOnly}
                onChange={(e) => setAtRiskOnly(e.target.checked)}
              />
              At-risk only
            </label>
            <select
              value={planFilter}
              onChange={(e) => setPlanFilter(e.target.value)}
              className="rounded-lg border border-border bg-bg-card px-3 py-1 text-sm text-text-primary"
            >
              <option value="">All plans</option>
              {['free', 'starter', 'growth', 'pro', 'scale'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          <div className="overflow-x-auto rounded-lg border border-border bg-bg-card">
            <table className="w-full text-sm">
              <thead className="bg-bg-elevated text-left text-xs text-text-muted">
                <tr>
                  <th className="px-3 py-2">User ID</th>
                  <th className="px-3 py-2">Plan</th>
                  <th className="px-3 py-2">Balance</th>
                  <th className="px-3 py-2">Revenue</th>
                  <th className="px-3 py-2">Cost</th>
                  <th className="px-3 py-2">Margin</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr
                    key={u.user_id}
                    className={`border-t border-border ${u.at_risk ? 'bg-red-500/5' : ''}`}
                  >
                    <td className="px-3 py-2 font-mono text-xs">{u.user_id.slice(0, 8)}…</td>
                    <td className="px-3 py-2">{u.plan}</td>
                    <td className="px-3 py-2">{u.balance.toLocaleString()}</td>
                    <td className="px-3 py-2">₹{u.revenue_inr.toLocaleString()}</td>
                    <td className="px-3 py-2">₹{u.cost_inr.toLocaleString()}</td>
                    <td
                      className={`px-3 py-2 ${
                        u.margin_inr < 0 ? 'text-red-400' : 'text-text-primary'
                      }`}
                    >
                      ₹{u.margin_inr.toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <TopUpButton userId={u.user_id} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Alerts Tab */}
      {tab === 'alerts' && (
        <div className="space-y-2">
          {alerts.length === 0 && (
            <div className="text-sm text-text-muted">No alerts in this window.</div>
          )}
          {alerts.map((a, i) => (
            <div
              key={i}
              className={`rounded-lg border p-3 ${
                a.severity === 'high'
                  ? 'border-red-500/30 bg-red-500/10'
                  : 'border-amber-500/30 bg-amber-500/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-text-muted">
                  {a.user_id.slice(0, 8)}…
                </span>
                <span className="text-xs uppercase tracking-wider text-text-muted">
                  {a.severity}
                </span>
              </div>
              <div className="mt-1 text-sm text-text-primary">{a.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: 'good' | 'warn' | 'bad';
}) {
  const color =
    tone === 'good'
      ? 'text-green-400'
      : tone === 'warn'
      ? 'text-amber-400'
      : tone === 'bad'
      ? 'text-red-400'
      : 'text-text-primary';
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="text-xs uppercase tracking-wider text-text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-text-muted">{sub}</div>}
    </div>
  );
}

function TopUpButton({ userId }: { userId: string }) {
  const [busy, setBusy] = useState(false);
  const handle = async () => {
    const raw = window.prompt(`Top-up credits for ${userId.slice(0, 8)}… — enter credits to add:`);
    if (!raw) return;
    const credits = parseInt(raw, 10);
    if (!Number.isFinite(credits) || credits <= 0) return;
    setBusy(true);
    try {
      const r = await adminTopUp({ user_id: userId, credits, reason: 'admin_topup' });
      alert(`New balance: ${r.balance.toLocaleString()} credits`);
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      disabled={busy}
      onClick={handle}
      className="rounded border border-border px-2 py-1 text-xs text-text-muted hover:border-accent hover:text-text-primary disabled:opacity-50"
    >
      Top-up
    </button>
  );
}
