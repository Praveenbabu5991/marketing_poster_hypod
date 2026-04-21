import { fetchApi } from './client';

export interface Overview {
  period_days: number;
  revenue_inr: number;
  cost_inr: number;
  margin_inr: number;
  margin_pct: number;
  user_count_by_plan: Record<string, number>;
  top_models: Array<{ model: string; cost_inr: number; calls: number }>;
  loss_makers_count: number;
}

export interface AdminUser {
  user_id: string;
  plan: string;
  balance: number;
  monthly_allowance: number;
  cost_inr: number;
  revenue_inr: number;
  margin_inr: number;
  at_risk: boolean;
}

export interface UsersResponse {
  items: AdminUser[];
  limit: number;
  offset: number;
  days: number;
}

export interface Alert {
  user_id: string;
  plan: string;
  cost_inr: number;
  plan_price: number;
  severity: 'medium' | 'high';
  type: string;
  message: string;
}

export interface AlertsResponse {
  alerts: Alert[];
  period_days: number;
}

export interface UserDetail {
  user_id: string;
  plan: string;
  balance: number;
  monthly_allowance: number;
  resets_at: string | null;
  stripe_customer_id: string | null;
  by_model: Array<{
    model: string;
    action_type: string;
    calls: number;
    cost_inr: number;
    credits_charged: number;
  }>;
  recent_transactions: Array<{
    id: string;
    delta: number;
    balance_after: number;
    reason: string;
    created_at: string;
  }>;
}

export function getOverview(days = 30): Promise<Overview> {
  return fetchApi<Overview>(`/api/v1/admin/overview?days=${days}`);
}

export function listUsers(
  opts: { plan?: string; at_risk?: boolean; limit?: number; offset?: number; days?: number } = {},
): Promise<UsersResponse> {
  const qs = new URLSearchParams();
  if (opts.plan) qs.set('plan', opts.plan);
  if (opts.at_risk) qs.set('at_risk', 'true');
  if (opts.limit) qs.set('limit', String(opts.limit));
  if (opts.offset) qs.set('offset', String(opts.offset));
  if (opts.days) qs.set('days', String(opts.days));
  return fetchApi<UsersResponse>(`/api/v1/admin/users?${qs.toString()}`);
}

export function getUserDetail(userId: string, days = 30): Promise<UserDetail> {
  return fetchApi<UserDetail>(`/api/v1/admin/users/${userId}?days=${days}`);
}

export function getAlerts(days = 7): Promise<AlertsResponse> {
  return fetchApi<AlertsResponse>(`/api/v1/admin/alerts?days=${days}`);
}

export function adminTopUp(data: {
  user_id: string;
  credits: number;
  reason?: string;
  note?: string;
}): Promise<{ user_id: string; balance: number; credited: number }> {
  return fetchApi('/api/v1/billing/admin-topup', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function adminSetPlan(data: {
  user_id: string;
  plan_id: string;
  top_up_credits?: boolean;
}): Promise<{ user_id: string; plan: string; balance: number; monthly_allowance: number }> {
  return fetchApi('/api/v1/billing/admin-set-plan', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
