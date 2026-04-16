import { fetchApi } from './client';
import type { CalendarPlan, CalendarSlot, CalendarSlotUpdate, CreateContentResponse } from '../types';

export function getPlan(brandId: string, year: number, month: number): Promise<CalendarPlan> {
  return fetchApi(`/api/v1/calendar/plans?brand_id=${brandId}&year=${year}&month=${month}`);
}

export function saveSlots(
  planId: string,
  slots: Array<{ date: string; event_name: string; event_type: string; post_idea: string; post_type: string; dialogue?: string }>,
): Promise<CalendarSlot[]> {
  return fetchApi(`/api/v1/calendar/plans/${planId}/slots`, {
    method: 'POST',
    body: JSON.stringify({ slots }),
  });
}

export function getSlots(planId: string): Promise<CalendarSlot[]> {
  return fetchApi(`/api/v1/calendar/plans/${planId}/slots`);
}

export function updateSlot(slotId: string, data: CalendarSlotUpdate): Promise<CalendarSlot> {
  return fetchApi(`/api/v1/calendar/slots/${slotId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function updatePlanSession(planId: string, plannerSessionId: string): Promise<CalendarPlan> {
  return fetchApi(`/api/v1/calendar/plans/${planId}`, {
    method: 'PATCH',
    body: JSON.stringify({ planner_session_id: plannerSessionId }),
  });
}

export function addSlot(
  planId: string,
  data: {
    date: string;
    event_name?: string;
    event_type?: string;
    post_idea?: string;
    post_type?: string;
    posting_time?: string;
    status?: string;
    session_id?: string;
    generated_image?: string;
    caption?: string;
    hashtags?: string;
    dialogue?: string;
    metadata_json?: Record<string, unknown>;
  },
): Promise<CalendarSlot> {
  return fetchApi(`/api/v1/calendar/plans/${planId}/slots/add`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function createSlotContent(slotId: string): Promise<CreateContentResponse> {
  return fetchApi(`/api/v1/calendar/slots/${slotId}/create-content`, {
    method: 'POST',
  });
}
