import { useEffect, useState } from 'react';
import {
  fetchUsageSummary,
  fetchUsageHistory,
  fetchUsageBreakdown,
  type BreakdownGroupBy,
  type BreakdownResponse,
} from '../api/usage';
import { getHistory as getCreditHistory, type CreditTransaction } from '../api/credits';
import { useStore } from '../store/useStore';
import type {
  UsageSummaryResponse,
  UsageSummaryItem,
  UsageHistoryResponse,
  UsageLogItem,
} from '../types';

const ACTION_LABELS: Record<string, string> = {
  text: 'Text / LLM',
  image: 'Image Gen',
  video: 'Video Gen',
  search: 'Search',
};

const ACTION_COLORS: Record<string, string> = {
  text: 'bg-blue-500/20 text-blue-400',
  image: 'bg-purple-500/20 text-purple-400',
  video: 'bg-amber-500/20 text-amber-400',
  search: 'bg-emerald-500/20 text-emerald-400',
};

function formatCost(usd: number): string {
  if (usd === 0) return '$0.00';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function shortModel(name: string): string {
  // "google_genai/gemini-2.5-flash" → "gemini-2.5-flash"
  return name.includes('/') ? name.split('/').pop()! : name;
}

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Summary Cards ────────────────────────────────────────────────

function SummaryCards({ summary }: { summary: UsageSummaryResponse }) {
  const totalCalls = summary.items.reduce((s, i) => s + i.total_calls, 0);
  const totalTokens = summary.items.reduce(
    (s, i) => s + i.total_prompt_tokens + i.total_completion_tokens,
    0,
  );
  const totalErrors = summary.items.reduce((s, i) => s + i.failed_calls, 0);

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard label="Total Cost" value={formatCost(summary.total_cost_usd)} accent />
      <StatCard label="API Calls" value={formatNumber(totalCalls)} />
      <StatCard label="Tokens Used" value={formatNumber(totalTokens)} />
      <StatCard
        label="Errors"
        value={String(totalErrors)}
        warn={totalErrors > 0}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <p className="text-xs font-medium text-text-muted">{label}</p>
      <p
        className={`mt-1 text-2xl font-bold ${
          accent
            ? 'text-accent'
            : warn
              ? 'text-red-400'
              : 'text-text-primary'
        }`}
      >
        {value}
      </p>
    </div>
  );
}

// ── Pivot Breakdown Panel ───────────────────────────────────────

const GROUP_LABELS: Record<BreakdownGroupBy, string> = {
  action: 'By Action',
  agent: 'By Agent',
  session: 'By Session',
  model: 'By Model',
};

const AGENT_LABELS: Record<string, string> = {
  single_post: 'Single Post',
  carousel: 'Carousel',
  campaign: 'Campaign',
  sales_poster: 'Sales Poster',
  ugc: 'UGC',
  product_ugc: 'Product UGC',
  motion_graphics: 'Motion Graphics',
  advertisement: 'Advertisement',
  content_calendar: 'Content Calendar',
  quick_image: 'Quick Image',
};

function prettyKey(groupBy: BreakdownGroupBy, key: string): string {
  if (groupBy === 'action') {
    return ACTION_LABELS[key] ?? key;
  }
  if (groupBy === 'agent') {
    return AGENT_LABELS[key] ?? key;
  }
  if (groupBy === 'model') return shortModel(key);
  return key;
}

function BreakdownPanel({
  groupBy,
  setGroupBy,
  data,
  loading,
}: {
  groupBy: BreakdownGroupBy;
  setGroupBy: (g: BreakdownGroupBy) => void;
  data: BreakdownResponse | null;
  loading: boolean;
}) {
  const items = data?.items ?? [];
  const total = data?.total_credits ?? 0;

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">
          Credit spend breakdown
        </h2>
        <div className="flex gap-1 rounded-lg border border-border p-0.5">
          {(Object.keys(GROUP_LABELS) as BreakdownGroupBy[]).map((g) => (
            <button
              key={g}
              onClick={() => setGroupBy(g)}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                groupBy === g
                  ? 'bg-accent text-white'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {GROUP_LABELS[g]}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-sm text-text-muted">Loading…</div>}

      {!loading && items.length === 0 && (
        <div className="py-8 text-center text-sm text-text-muted">
          No usage yet for this window.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="space-y-2">
          {items.map((item) => {
            const pct = total > 0 ? (item.credits / total) * 100 : 0;
            const label =
              groupBy === 'session'
                ? item.label || '(untitled)'
                : prettyKey(groupBy, item.key);
            const sub =
              groupBy === 'session' && item.agent_type
                ? AGENT_LABELS[item.agent_type] ?? item.agent_type
                : null;
            return (
              <div key={item.key} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <div className="min-w-0 flex-1 truncate pr-3 text-text-primary">
                    {label}
                    {sub && (
                      <span className="ml-2 text-xs text-text-muted">({sub})</span>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs text-text-muted">
                    <span>{item.calls} {item.calls === 1 ? 'call' : 'calls'}</span>
                    <span className="w-20 text-right font-semibold text-text-primary">
                      {item.credits.toLocaleString()} credits
                    </span>
                    <span className="w-12 text-right">{pct.toFixed(0)}%</span>
                  </div>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-page">
                  <div
                    className="h-full bg-accent"
                    style={{ width: `${Math.max(1, pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
          <div className="mt-3 flex justify-end border-t border-border pt-3 text-sm font-semibold text-text-primary">
            Total: {total.toLocaleString()} credits
          </div>
        </div>
      )}
    </div>
  );
}

// ── Per-Model Breakdown ──────────────────────────────────────────

function ModelBreakdown({ items }: { items: UsageSummaryItem[] }) {
  if (items.length === 0) return null;

  // Sort by cost descending
  const sorted = [...items].sort((a, b) => b.total_cost_usd - a.total_cost_usd);
  const maxCost = sorted[0]?.total_cost_usd || 1;

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-text-primary">
        Cost by Model & Action
      </h3>
      <div className="space-y-3">
        {sorted.map((item, i) => (
          <div key={i}>
            <div className="mb-1 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${ACTION_COLORS[item.action_type] || 'bg-gray-500/20 text-gray-400'}`}
                >
                  {ACTION_LABELS[item.action_type] || item.action_type}
                </span>
                <span className="text-xs text-text-primary">
                  {shortModel(item.model_name)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-text-muted">
                  {item.total_calls} calls
                </span>
                <span className="text-xs font-medium text-text-primary">
                  {formatCost(item.total_cost_usd)}
                </span>
              </div>
            </div>
            {/* Bar */}
            <div className="h-1.5 overflow-hidden rounded-full bg-bg-elevated">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{
                  width: `${maxCost > 0 ? (item.total_cost_usd / maxCost) * 100 : 0}%`,
                }}
              />
            </div>
            {/* Detail row */}
            <div className="mt-1 flex gap-4 text-[10px] text-text-muted">
              {item.total_prompt_tokens + item.total_completion_tokens > 0 && (
                <span>
                  {formatNumber(item.total_prompt_tokens + item.total_completion_tokens)}{' '}
                  tokens
                </span>
              )}
              {item.total_video_seconds > 0 && (
                <span>{item.total_video_seconds}s video</span>
              )}
              <span className="text-green-400">
                {item.successful_calls} ok
              </span>
              {item.failed_calls > 0 && (
                <span className="text-red-400">
                  {item.failed_calls} failed
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── History Table ────────────────────────────────────────────────

function HistoryTable({
  history,
  loading,
  filterAction,
  setFilterAction,
  page,
  setPage,
  pageSize,
}: {
  history: UsageHistoryResponse;
  loading: boolean;
  filterAction: string;
  setFilterAction: (v: string) => void;
  page: number;
  setPage: (p: number) => void;
  pageSize: number;
}) {
  const totalPages = Math.ceil(history.total / pageSize);

  return (
    <div className="rounded-xl border border-border bg-bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold text-text-primary">
          Usage History
          <span className="ml-2 text-xs font-normal text-text-muted">
            ({history.total} total)
          </span>
        </h3>
        {/* Filter */}
        <select
          value={filterAction}
          onChange={(e) => {
            setFilterAction(e.target.value);
            setPage(0);
          }}
          className="rounded-lg border border-border bg-bg-page px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">All types</option>
          <option value="text">Text / LLM</option>
          <option value="image">Image Gen</option>
          <option value="video">Video Gen</option>
          <option value="search">Search</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="px-5 py-2 font-medium">Time</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Model</th>
              <th className="px-3 py-2 font-medium">Tool</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 text-right font-medium">Tokens</th>
              <th className="px-5 py-2 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-text-muted">
                  Loading...
                </td>
              </tr>
            ) : history.items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-text-muted">
                  No usage logs yet. Start a chat to see activity here.
                </td>
              </tr>
            ) : (
              history.items.map((item) => (
                <HistoryRow key={item.id} item={item} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="rounded-lg border border-border px-3 py-1 text-xs text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-primary disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-xs text-text-muted">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1}
            className="rounded-lg border border-border px-3 py-1 text-xs text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-primary disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function HistoryRow({ item }: { item: UsageLogItem }) {
  const [expanded, setExpanded] = useState(false);
  const tokens =
    (item.prompt_tokens || 0) + (item.completion_tokens || 0);

  return (
    <>
      <tr
        onClick={() => item.error_message && setExpanded(!expanded)}
        className={`border-b border-border/50 transition-colors hover:bg-bg-elevated/50 ${
          item.error_message ? 'cursor-pointer' : ''
        }`}
      >
        <td className="px-5 py-2.5 text-text-muted">
          {item.created_at ? timeAgo(item.created_at) : '-'}
        </td>
        <td className="px-3 py-2.5">
          <span
            className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${ACTION_COLORS[item.action_type] || 'bg-gray-500/20 text-gray-400'}`}
          >
            {ACTION_LABELS[item.action_type] || item.action_type}
          </span>
        </td>
        <td className="px-3 py-2.5 text-text-primary">
          {shortModel(item.model_name)}
        </td>
        <td className="px-3 py-2.5 text-text-muted">
          {item.tool_name || '-'}
        </td>
        <td className="px-3 py-2.5">
          {item.status === 'success' ? (
            <span className="text-green-400">OK</span>
          ) : (
            <span className="text-red-400">Error</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-right text-text-muted">
          {tokens > 0 ? formatNumber(tokens) : item.video_duration_seconds ? `${item.video_duration_seconds}s` : '-'}
        </td>
        <td className="px-5 py-2.5 text-right font-medium text-text-primary">
          {formatCost(item.cost_usd)}
        </td>
      </tr>
      {expanded && item.error_message && (
        <tr className="border-b border-border/50">
          <td colSpan={7} className="bg-red-500/5 px-5 py-2 text-[11px] text-red-300">
            {item.error_message}
          </td>
        </tr>
      )}
    </>
  );
}

// ── Date Range Picker ────────────────────────────────────────────

function DateFilter({
  startDate,
  endDate,
  setStartDate,
  setEndDate,
}: {
  startDate: string;
  endDate: string;
  setStartDate: (v: string) => void;
  setEndDate: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
        className="rounded-lg border border-border bg-bg-page px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none [color-scheme:dark]"
      />
      <span className="text-xs text-text-muted">to</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
        className="rounded-lg border border-border bg-bg-page px-3 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none [color-scheme:dark]"
      />
      {(startDate || endDate) && (
        <button
          onClick={() => {
            setStartDate('');
            setEndDate('');
          }}
          className="text-xs text-text-muted hover:text-accent"
        >
          Clear
        </button>
      )}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────

export function Usage() {
  const [summary, setSummary] = useState<UsageSummaryResponse | null>(null);
  const [history, setHistory] = useState<UsageHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [tab, setTab] = useState<'usage' | 'transactions'>('usage');
  const [creditTx, setCreditTx] = useState<CreditTransaction[]>([]);
  const [txLoading, setTxLoading] = useState(false);
  const { credits, refreshCredits } = useStore();

  useEffect(() => {
    refreshCredits();
  }, []);

  useEffect(() => {
    if (tab !== 'transactions') return;
    setTxLoading(true);
    getCreditHistory(0, 100)
      .then((r) => setCreditTx(r.items))
      .catch(console.error)
      .finally(() => setTxLoading(false));
  }, [tab]);

  // Filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 25;

  // Pivot
  const [groupBy, setGroupBy] = useState<BreakdownGroupBy>('action');
  const [breakdown, setBreakdown] = useState<BreakdownResponse | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);

  useEffect(() => {
    if (tab !== 'usage') return;
    setBreakdownLoading(true);
    fetchUsageBreakdown({
      group_by: groupBy,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    })
      .then(setBreakdown)
      .catch(console.error)
      .finally(() => setBreakdownLoading(false));
  }, [tab, groupBy, startDate, endDate]);

  // Fetch summary when date range changes
  useEffect(() => {
    setLoading(true);
    fetchUsageSummary(startDate || undefined, endDate || undefined)
      .then(setSummary)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [startDate, endDate]);

  // Fetch history when filters/page change
  useEffect(() => {
    setHistoryLoading(true);
    fetchUsageHistory({
      limit: pageSize,
      offset: page * pageSize,
      action_type: filterAction || undefined,
    })
      .then(setHistory)
      .catch(console.error)
      .finally(() => setHistoryLoading(false));
  }, [filterAction, page]);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Usage & Costs</h1>
          <p className="mt-1 text-sm text-text-muted">
            Monitor your API usage across all models
          </p>
        </div>
        {tab === 'usage' && (
          <DateFilter
            startDate={startDate}
            endDate={endDate}
            setStartDate={setStartDate}
            setEndDate={setEndDate}
          />
        )}
      </div>

      {/* Credit balance panel */}
      {credits && (
        <div className="mb-6 rounded-lg border border-border bg-bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-text-muted">
                Your Credits
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-3xl font-bold text-text-primary">
                  {credits.balance.toLocaleString()}
                </span>
                {credits.monthly_allowance > 0 && (
                  <span className="text-sm text-text-muted">
                    / {credits.monthly_allowance.toLocaleString()} monthly
                  </span>
                )}
              </div>
              <div className="mt-1 text-xs text-text-muted">
                Plan: <span className="text-text-primary">{credits.plan}</span>
                {credits.resets_at && (
                  <>
                    {' '}
                    · Resets{' '}
                    <span className="text-text-primary">
                      {new Date(credits.resets_at).toLocaleDateString()}
                    </span>
                  </>
                )}
              </div>
            </div>
            {credits.monthly_allowance > 0 && (
              <div className="w-40">
                <div className="h-2 w-full overflow-hidden rounded-full bg-bg-page">
                  <div
                    className="h-full bg-accent"
                    style={{
                      width: `${Math.max(0, Math.min(100, (credits.balance / credits.monthly_allowance) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-1 border-b border-border">
        <button
          onClick={() => setTab('usage')}
          className={`px-4 py-2 text-sm font-medium ${
            tab === 'usage'
              ? 'border-b-2 border-accent text-text-primary'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          Usage & Models
        </button>
        <button
          onClick={() => setTab('transactions')}
          className={`px-4 py-2 text-sm font-medium ${
            tab === 'transactions'
              ? 'border-b-2 border-accent text-text-primary'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          Credit Transactions
        </button>
      </div>

      {tab === 'usage' &&
        (loading ? (
          <div className="flex items-center justify-center py-20 text-text-muted">
            Loading usage data...
          </div>
        ) : summary ? (
          <div className="space-y-6">
            <SummaryCards summary={summary} />
            <BreakdownPanel
              groupBy={groupBy}
              setGroupBy={setGroupBy}
              data={breakdown}
              loading={breakdownLoading}
            />
            <ModelBreakdown items={summary.items} />
            <HistoryTable
              history={
                history || { items: [], total: 0, limit: pageSize, offset: 0 }
              }
              loading={historyLoading}
              filterAction={filterAction}
              setFilterAction={setFilterAction}
              page={page}
              setPage={setPage}
              pageSize={pageSize}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-text-muted">
            Failed to load usage data
          </div>
        ))}

      {tab === 'transactions' && (
        <div className="rounded-lg border border-border bg-bg-card">
          {txLoading && <div className="p-6 text-text-muted">Loading…</div>}
          {!txLoading && creditTx.length === 0 && (
            <div className="p-6 text-text-muted">No transactions yet.</div>
          )}
          {!txLoading && creditTx.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-bg-elevated text-left text-xs text-text-muted">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Reason</th>
                  <th className="px-3 py-2">Delta</th>
                  <th className="px-3 py-2">Balance After</th>
                </tr>
              </thead>
              <tbody>
                {creditTx.map((t) => (
                  <tr key={t.id} className="border-t border-border">
                    <td className="px-3 py-2 text-text-muted">
                      {new Date(t.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-text-primary">{t.reason}</td>
                    <td
                      className={`px-3 py-2 font-mono ${
                        t.delta < 0 ? 'text-red-400' : 'text-green-400'
                      }`}
                    >
                      {t.delta > 0 ? '+' : ''}
                      {t.delta}
                    </td>
                    <td className="px-3 py-2">{t.balance_after.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
