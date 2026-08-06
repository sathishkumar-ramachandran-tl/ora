// Agentic Module Generation (Phase 1) — marketplace browse/install/generate calls.
import { apiV2Client } from './client';
import {
  ModuleSummary, ModuleDetail, ModuleGenerationDraft, ModuleProgress,
  ModuleInstance, ModuleCategory, ModuleDifficulty, ModuleMilestoneSpec,
} from '../types';

export const browseModules = async (category?: ModuleCategory): Promise<ModuleSummary[]> => {
  const res = await apiV2Client.get<ModuleSummary[]>('/modules', { params: category ? { category } : {} });
  return res.data;
};

export const getMyModules = async (): Promise<ModuleSummary[]> => {
  const res = await apiV2Client.get<ModuleSummary[]>('/modules/mine');
  return res.data;
};

export const getModule = async (moduleTemplateId: string): Promise<ModuleDetail> => {
  const res = await apiV2Client.get<ModuleDetail>(`/modules/${moduleTemplateId}`);
  return res.data;
};

export const generateModule = async (
  goal: string,
  title?: string,
  category: ModuleCategory = 'general',
  difficulty: ModuleDifficulty = 'intermediate'
): Promise<ModuleGenerationDraft> => {
  const res = await apiV2Client.post<ModuleGenerationDraft>('/modules', { goal, title, category, difficulty });
  return res.data;
};

export const getGenerationProgress = async (moduleTemplateId: string): Promise<ModuleProgress> => {
  const res = await apiV2Client.get<ModuleProgress>(`/modules/${moduleTemplateId}/progress`);
  return res.data;
};

export const updateModuleStructure = async (
  moduleTemplateId: string, milestones: ModuleMilestoneSpec[]
): Promise<{ id: string; structure: { milestones: ModuleMilestoneSpec[] }; milestoneCount: number; taskCount: number }> => {
  const res = await apiV2Client.patch(`/modules/${moduleTemplateId}/structure`, { milestones });
  return res.data;
};

export const publishModule = async (moduleTemplateId: string): Promise<void> => {
  await apiV2Client.post(`/modules/${moduleTemplateId}/publish`);
};

export const installModule = async (
  moduleTemplateId: string, workspaceId: string, companyId?: string
): Promise<{ moduleInstanceId: string; projectId: string }> => {
  const res = await apiV2Client.post(`/modules/${moduleTemplateId}/install`, { workspaceId, companyId });
  return res.data;
};

export const getModuleInstance = async (moduleInstanceId: string): Promise<ModuleInstance> => {
  const res = await apiV2Client.get<ModuleInstance>(`/modules/instances/${moduleInstanceId}`);
  return res.data;
};
