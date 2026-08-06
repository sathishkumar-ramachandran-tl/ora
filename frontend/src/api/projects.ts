import { apiClient } from './client';
import {
  CanvasItem, Company, Project, User,
  Milestone, Sprint, TaskDependency, TaskDependencies, BlockedTaskEntry, ReplanResult,
} from '../types';

export const createCompany = async (company: Company): Promise<void> => {
  await apiClient.post('/companies', company);
};

export const createProject = async (project: Project, companyId: string): Promise<void> => {
  await apiClient.post(`/companies/${companyId}/projects`, project);
};

export const getProjectMembers = async (projectId: string): Promise<User[]> => {
  const res = await apiClient.get(`/projects/${projectId}/members`);
  return res.data;
};

export const assignUserToProject = async (projectId: string, userId: string, role: string = 'contributor'): Promise<any> => {
  const res = await apiClient.post(`/projects/${projectId}/assign-member`, { userId, role });
  return res.data;
};

export const removeUserFromProject = async (projectId: string, memberId: string): Promise<void> => {
  await apiClient.delete(`/projects/${projectId}/members/${memberId}`);
};

export const saveWhiteboard = async (contextType: 'company' | 'project', id: string, items: CanvasItem[]): Promise<void> => {
  const endpoint = contextType === 'company' ? 'companies' : 'projects';
  await apiClient.patch(`/${endpoint}/${id}/whiteboard`, { items });
};

// --- Milestones ---

export const listMilestones = async (projectId: string): Promise<Milestone[]> => {
  const res = await apiClient.get(`/projects/${projectId}/milestones`);
  return res.data;
};

export const createMilestone = async (
  projectId: string,
  data: { title: string; description?: string; dueDate?: string; order?: number }
): Promise<Milestone> => {
  const res = await apiClient.post(`/projects/${projectId}/milestones`, data);
  return res.data;
};

export const updateMilestone = async (
  milestoneId: string,
  data: Partial<Pick<Milestone, 'title' | 'description' | 'dueDate' | 'status' | 'order'>>
): Promise<Milestone> => {
  const res = await apiClient.patch(`/projects/milestones/${milestoneId}`, data);
  return res.data;
};

export const deleteMilestone = async (milestoneId: string): Promise<void> => {
  await apiClient.delete(`/projects/milestones/${milestoneId}`);
};

// --- Sprints ---

export const listSprints = async (projectId: string): Promise<Sprint[]> => {
  const res = await apiClient.get(`/projects/${projectId}/sprints`);
  return res.data;
};

export const createSprint = async (
  projectId: string,
  data: { name: string; startDate?: string; endDate?: string; status?: string }
): Promise<Sprint> => {
  const res = await apiClient.post(`/projects/${projectId}/sprints`, data);
  return res.data;
};

export const updateSprint = async (
  sprintId: string,
  data: Partial<Pick<Sprint, 'name' | 'startDate' | 'endDate' | 'status'>>
): Promise<Sprint> => {
  const res = await apiClient.patch(`/projects/sprints/${sprintId}`, data);
  return res.data;
};

export const deleteSprint = async (sprintId: string): Promise<void> => {
  await apiClient.delete(`/projects/sprints/${sprintId}`);
};

// --- Task Dependencies ---

export const getTaskDependencies = async (taskId: string): Promise<TaskDependencies> => {
  const res = await apiClient.get(`/tasks/${taskId}/dependencies`);
  return res.data;
};

export const addTaskDependency = async (
  taskId: string, dependsOnTaskId: string, type: string = 'blocks'
): Promise<TaskDependency> => {
  const res = await apiClient.post(`/tasks/${taskId}/dependencies`, { dependsOnTaskId, type });
  return res.data;
};

export const removeTaskDependency = async (dependencyId: string): Promise<void> => {
  await apiClient.delete(`/tasks/dependencies/${dependencyId}`);
};

export const getBlockedTasks = async (projectId: string): Promise<BlockedTaskEntry[]> => {
  const res = await apiClient.get(`/projects/${projectId}/blocked-tasks`);
  return res.data;
};

// --- AI Replanning ---

export const replanProject = async (projectId: string, goal: string): Promise<ReplanResult> => {
  const res = await apiClient.post(`/projects/${projectId}/replan`, { goal });
  return res.data;
};
