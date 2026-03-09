import { fetchApi } from './client';
import type { Agent } from '../types';

export function listAgents(): Promise<Agent[]> {
  return fetchApi<Agent[]>('/api/v1/agents');
}
