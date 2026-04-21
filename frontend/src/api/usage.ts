import { fetchApi } from './client';
import type { UsageSummaryResponse, UsageHistoryResponse } from '../types';

export type BreakdownGroupBy = 'action' | 'agent' | 'session' | 'model';

export interface BreakdownItem {
  key: string;
  calls: number;
  credits: number;
  cost_usd: number;
  label?: string;
  agent_type?: string;
}

export interface BreakdownResponse {
  group_by: BreakdownGroupBy;
  items: BreakdownItem[];
  total_credits: number;
  total_cost_usd: number;
}

export async function fetchUsageBreakdown(opts: {
  group_by: BreakdownGroupBy;
  start_date?: string;
  end_date?: string;
}): Promise<BreakdownResponse> {
  const params = new URLSearchParams({ group_by: opts.group_by });
  if (opts.start_date) params.set('start_date', opts.start_date);
  if (opts.end_date) params.set('end_date', opts.end_date);
  return fetchApi<BreakdownResponse>(`/api/v1/usage/breakdown?${params.toString()}`);
}

export async function fetchUsageSummary(
  startDate?: string,
  endDate?: string,
): Promise<UsageSummaryResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const qs = params.toString();
  return fetchApi<UsageSummaryResponse>(`/api/v1/usage/summary${qs ? `?${qs}` : ''}`);
}

export async function fetchUsageHistory(opts: {
  limit?: number;
  offset?: number;
  action_type?: string;
  model_name?: string;
} = {}): Promise<UsageHistoryResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts.action_type) params.set('action_type', opts.action_type);
  if (opts.model_name) params.set('model_name', opts.model_name);
  const qs = params.toString();
  return fetchApi<UsageHistoryResponse>(`/api/v1/usage/history${qs ? `?${qs}` : ''}`);
}
