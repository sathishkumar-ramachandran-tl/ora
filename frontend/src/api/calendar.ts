import { apiClient } from './client';
import { CalendarEvent, Task } from '../types';

export const getEvents = async (
  workspaceId: string, start?: Date, end?: Date, scope?: CalendarEvent['scope'],
): Promise<CalendarEvent[]> => {
  const params: any = {};
  if (start) params.start = start.toISOString();
  if (end) params.end = end.toISOString();
  if (scope) params.scope = scope;
  const res = await apiClient.get(`/workspaces/${workspaceId}/events`, { params });
  return res.data;
};

export const createEvent = async (workspaceId: string, event: Partial<CalendarEvent>): Promise<CalendarEvent> => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/events`, {
    title: event.title,
    start: event.start,
    end: event.end,
    type: event.type,
    scope: event.scope,
    taskId: event.taskId,
    color: event.color,
    timezone: event.timezone,
    recurrenceRule: event.recurrenceRule,
    attendees: event.attendees,
    organizationId: event.organizationId,
  });
  return res.data;
};

export const updateEvent = async (eventId: string, patch: Partial<CalendarEvent>): Promise<CalendarEvent> => {
  const res = await apiClient.patch(`/events/${eventId}`, patch);
  return res.data;
};

export const deleteEvent = async (eventId: string, deleteSeries = false): Promise<void> => {
  await apiClient.delete(`/events/${eventId}`, { params: deleteSeries ? { deleteSeries: true } : undefined });
};

export const findAvailability = async (
  workspaceId: string,
  opts: { attendeeUserIds?: string[]; durationMinutes: number; windowStart: Date; windowEnd: Date; dayStartHour?: number; dayEndHour?: number },
): Promise<{ slots: { start: string; end: string }[]; attendeeCount: number }> => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/availability`, {
    attendeeUserIds: opts.attendeeUserIds,
    durationMinutes: opts.durationMinutes,
    windowStart: opts.windowStart.toISOString(),
    windowEnd: opts.windowEnd.toISOString(),
    dayStartHour: opts.dayStartHour,
    dayEndHour: opts.dayEndHour,
  });
  return res.data;
};

export const scheduleModuleMilestones = async (
  workspaceId: string, moduleInstanceId: string, blockHours = 2.0,
): Promise<{ scheduledCount: number; events: any[] }> => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/modules/${moduleInstanceId}/schedule`, { blockHours });
  return res.data;
};

export const optimizeSchedule = async (tasks: Task[], date: Date): Promise<CalendarEvent[]> => {
  const res = await apiClient.post('/agents/optimize-schedule', {
    tasks,
    date: date.toISOString().split('T')[0]
  });
  return res.data;
};

export interface AutoScheduleConstraints {
  taskIds?: string[];
  instruction?: string;
  dayStartHour?: number;
  dayEndHour?: number;
  weekdaysOnly?: boolean;
  targetEndDate?: string; // ISO date
  blockHours?: number;
}

export interface AutoScheduleResult {
  scheduledCount: number;
  scheduled: { taskId: string; title: string; eventId: string; start: string; end: string }[];
  unscheduledCount: number;
  unscheduled: { taskId: string; title: string }[];
}

export const autoScheduleTasks = async (
  workspaceId: string, constraints: AutoScheduleConstraints = {}
): Promise<AutoScheduleResult> => {
  const res = await apiClient.post(`/workspaces/${workspaceId}/auto-schedule`, constraints);
  return res.data;
};
