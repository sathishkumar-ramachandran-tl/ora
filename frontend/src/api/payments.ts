// Agent Economy — Circle/USDC autonomous capability purchases.
import { apiV2Client } from './client';
import {
  AgentWalletInfo, EconomicPolicySettings, SpendingSummary, CapabilityProviderInfo,
  EconomicActionSummary, EconomicActionDetail, PaymentTransactionSummary,
} from '../types';

export const getWallet = async (workspaceId: string): Promise<AgentWalletInfo> => {
  const res = await apiV2Client.get<AgentWalletInfo>(`/payments/workspaces/${workspaceId}/wallet`);
  return res.data;
};

export const createWallet = async (workspaceId: string): Promise<AgentWalletInfo> => {
  const res = await apiV2Client.post<AgentWalletInfo>(`/payments/workspaces/${workspaceId}/wallet`);
  return res.data;
};

export const listTransactions = async (workspaceId: string): Promise<PaymentTransactionSummary[]> => {
  const res = await apiV2Client.get<PaymentTransactionSummary[]>(`/payments/workspaces/${workspaceId}/transactions`);
  return res.data;
};

export const getSpendingSummary = async (workspaceId: string): Promise<SpendingSummary> => {
  const res = await apiV2Client.get<SpendingSummary>(`/payments/workspaces/${workspaceId}/spending-summary`);
  return res.data;
};

export const getPolicy = async (workspaceId: string): Promise<EconomicPolicySettings> => {
  const res = await apiV2Client.get<EconomicPolicySettings>(`/payments/workspaces/${workspaceId}/policy`);
  return res.data;
};

export const updatePolicy = async (
  workspaceId: string, patch: Partial<EconomicPolicySettings>
): Promise<void> => {
  await apiV2Client.patch(`/payments/workspaces/${workspaceId}/policy`, patch);
};

export const listCapabilities = async (capability?: string): Promise<CapabilityProviderInfo[]> => {
  const res = await apiV2Client.get<CapabilityProviderInfo[]>('/payments/capabilities', {
    params: capability ? { capability } : {},
  });
  return res.data;
};

export const acquireCapability = async (
  workspaceId: string, capability: string, task: string, reason?: string,
  constraints?: { max_cost_usdc?: number; max_latency_ms?: number }
): Promise<{ success: boolean; data: Record<string, unknown> | null; error: string | null }> => {
  const res = await apiV2Client.post(`/payments/workspaces/${workspaceId}/capabilities/acquire`, {
    capability, task, reason, ...constraints,
  }, { validateStatus: () => true });
  return res.data;
};

export const listEconomicActions = async (workspaceId: string): Promise<EconomicActionSummary[]> => {
  const res = await apiV2Client.get<EconomicActionSummary[]>(`/payments/workspaces/${workspaceId}/economic-actions`);
  return res.data;
};

export const getEconomicAction = async (workspaceId: string, actionId: string): Promise<EconomicActionDetail> => {
  const res = await apiV2Client.get<EconomicActionDetail>(
    `/payments/workspaces/${workspaceId}/economic-actions/${actionId}`
  );
  return res.data;
};

export const approveEconomicAction = async (workspaceId: string, actionId: string) => {
  const res = await apiV2Client.post(
    `/payments/workspaces/${workspaceId}/economic-actions/${actionId}/approve`,
    {}, { validateStatus: () => true }
  );
  return res.data;
};

export const rejectEconomicAction = async (workspaceId: string, actionId: string, note?: string) => {
  const res = await apiV2Client.post(
    `/payments/workspaces/${workspaceId}/economic-actions/${actionId}/reject`,
    { note }, { validateStatus: () => true }
  );
  return res.data;
};
