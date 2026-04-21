import { fetchApi } from './client';

export interface Balance {
  user_id: string;
  plan: string;
  balance: number;
  monthly_allowance: number;
  resets_at: string | null;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export interface EstimateResponse {
  action: string;
  credits: number;
  inr: number;
}

export interface CreditTransaction {
  id: string;
  delta: number;
  balance_after: number;
  reason: string;
  usage_log_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface HistoryResponse {
  items: CreditTransaction[];
  total: number;
  limit: number;
  offset: number;
}

export function getBalance(): Promise<Balance> {
  return fetchApi<Balance>('/api/v1/credits/balance');
}

export function estimate(
  action: 'llm_text' | 'image' | 'video' | 'search',
  opts: { duration_sec?: number } = {},
): Promise<EstimateResponse> {
  const qs = new URLSearchParams({ action });
  if (opts.duration_sec != null) qs.set('duration_sec', String(opts.duration_sec));
  return fetchApi<EstimateResponse>(`/api/v1/credits/estimate?${qs.toString()}`);
}

export function getHistory(
  offset = 0,
  limit = 50,
  reason?: string,
): Promise<HistoryResponse> {
  const qs = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (reason) qs.set('reason', reason);
  return fetchApi<HistoryResponse>(`/api/v1/credits/history?${qs.toString()}`);
}
