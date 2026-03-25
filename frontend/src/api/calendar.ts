import { fetchApi } from './client';
import type { CalendarPlan, CalendarSlot, CalendarSlotUpdate, CreateContentResponse } from '../types';

export function getPlan(brandId: string, year: number, month: number): Promise<CalendarPlan> {
  return fetchApi(`/api/v1/calendar/plans?brand_id=${brandId}&year=${year}&month=${month}`);
}

export function saveSlots(
  planId: string,
  slots: Array<{ date: string; event_name: string; event_type: string; post_idea: string; post_type: string }>,
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

export function createSlotContent(slotId: string): Promise<CreateContentResponse> {
  return fetchApi(`/api/v1/calendar/slots/${slotId}/create-content`, {
    method: 'POST',
  });
}
