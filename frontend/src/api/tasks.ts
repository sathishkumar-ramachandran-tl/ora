import { apiClient } from './client';
import { Task, TaskResource } from '../types';

export const addTasks = async (tasks: Task[], projectId: string): Promise<void> => {
  await apiClient.post(`/projects/${projectId}/tasks`, { tasks });
};

export const updateTaskStatus = async (taskId: string, status: string): Promise<void> => {
  await apiClient.patch(`/tasks/${taskId}`, { status });
};

export const updateTaskResources = async (taskId: string, resources: TaskResource[]): Promise<void> => {
  await apiClient.patch(`/tasks/${taskId}`, { resources });
};

export const toggleTaskDailyFocus = async (taskId: string, isFocused: boolean): Promise<void> => {
  await apiClient.patch(`/tasks/${taskId}`, { isDailyFocus: isFocused });
};
