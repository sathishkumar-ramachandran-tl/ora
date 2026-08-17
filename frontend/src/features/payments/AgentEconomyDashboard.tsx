import React, { useState, useEffect, useCallback } from 'react';
import {
  Wallet, Loader2, ShieldCheck, ShieldAlert, ShieldX, ExternalLink, Zap, Store,
  Settings2, PlayCircle, CheckCircle2, XCircle, AlertTriangle, Copy,
} from 'lucide-react';
import * as paymentsApi from '../../api/payments';
import {
  AgentWalletInfo, EconomicPolicySettings, SpendingSummary, CapabilityProviderInfo,
  EconomicActionSummary, PaymentTransactionSummary,
} from '../../types';

interface AgentEconomyDashboardProps {
  workspaceId: string;
}

const STATUS_STYLE: Record<string, { label: string; dot: string; text: string }> = {
  PROPOSED: { label: 'Proposed', dot: 'bg-slate-400', text: 'text-slate-500' },
  POLICY_CHECK: { label: 'Awaiting policy', dot: 'bg-amber-500', text: 'text-amber-600' },
  APPROVED: { label: 'Approved', dot: 'bg-sky-500', text: 'text-sky-600' },
  REJECTED: { label: 'Rejected', dot: 'bg-rose-500', text: 'text-rose-600' },
  PAYMENT_PENDING: { label: 'Paying…', dot: 'bg-amber-500', text: 'text-amber-600' },
  PAID: { label: 'Paid', dot: 'bg-sky-500', text: 'text-sky-600' },
  PAYMENT_FAILED: { label: 'Payment failed', dot: 'bg-rose-500', text: 'text-rose-600' },
  SERVICE_EXECUTING: { label: 'Running…', dot: 'bg-amber-500', text: 'text-amber-600' },
  SERVICE_FAILED: { label: 'Service failed', dot: 'bg-rose-500', text: 'text-rose-600' },
  RESULT_RECEIVED: { label: 'Verifying…', dot: 'bg-amber-500', text: 'text-amber-600' },
  VERIFIED: { label: 'Verified', dot: 'bg-emerald-500', text: 'text-emerald-600' },
  VERIFICATION_FAILED: { label: 'Verification failed', dot: 'bg-rose-500', text: 'text-rose-600' },
  REFUND_PENDING: { label: 'Refund pending', dot: 'bg-orange-500', text: 'text-orange-600' },
  CANCELLED: { label: 'Cancelled', dot: 'bg-slate-400', text: 'text-slate-500' },
};

const fmtUsdc = (n: number | null | undefined) => n === null || n === undefined ? '—' : `$${n.toFixed(4)}`;

const StatCard: React.FC<{ label: string; value: React.ReactNode; sub?: React.ReactNode; icon: React.ReactNode }> = (
  { label, value, sub, icon }
) => (
  <div className="rounded-2xl border border-slate-200/70 bg-white p-4">
    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
      {icon} {label}
    </div>
    <p className="text-2xl font-semibold text-slate-900 tracking-tight">{value}</p>
    {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
  </div>
);

export const AgentEconomyDashboard: React.FC<AgentEconomyDashboardProps> = ({ workspaceId }) => {
  const [wallet, setWallet] = useState<AgentWalletInfo | null>(null);
  const [spending, setSpending] = useState<SpendingSummary | null>(null);
  const [actions, setActions] = useState<EconomicActionSummary[]>([]);
  const [transactions, setTransactions] = useState<PaymentTransactionSummary[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityProviderInfo[]>([]);
  const [policy, setPolicy] = useState<EconomicPolicySettings | null>(null);
  const [policyDraft, setPolicyDraft] = useState<EconomicPolicySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingWallet, setCreatingWallet] = useState(false);
  const [busyActionId, setBusyActionId] = useState<string | null>(null);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [testForm, setTestForm] = useState({ capability: '', task: '' });
  const [testBusy, setTestBusy] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [w, s, a, t, c, p] = await Promise.all([
        paymentsApi.getWallet(workspaceId),
        paymentsApi.getSpendingSummary(workspaceId),
        paymentsApi.listEconomicActions(workspaceId),
        paymentsApi.listTransactions(workspaceId),
        paymentsApi.listCapabilities(),
        paymentsApi.getPolicy(workspaceId),
      ]);
      setWallet(w); setSpending(s); setActions(a); setTransactions(t); setCapabilities(c);
      setPolicy(p); setPolicyDraft(p);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { load(); }, [load]);

  const handleCreateWallet = async () => {
    setCreatingWallet(true);
    try { await paymentsApi.createWallet(workspaceId); await load(); } finally { setCreatingWallet(false); }
  };

  const handleApprove = async (id: string) => {
    setBusyActionId(id);
    try { await paymentsApi.approveEconomicAction(workspaceId, id); await load(); } finally { setBusyActionId(null); }
  };

  const handleReject = async (id: string) => {
    setBusyActionId(id);
    try { await paymentsApi.rejectEconomicAction(workspaceId, id); await load(); } finally { setBusyActionId(null); }
  };

  const handleRunTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testForm.capability || !testForm.task) return;
    setTestBusy(true);
    setTestResult(null);
    try {
      const res = await paymentsApi.acquireCapability(workspaceId, testForm.capability, testForm.task);
      setTestResult({
        ok: !!res.success,
        message: res.success ? 'Capability acquired and verified.' : (res.error || 'Purchase failed.'),
      });
      await load();
    } finally {
      setTestBusy(false);
    }
  };

  const handleSavePolicy = async () => {
    if (!policyDraft) return;
    setSavingPolicy(true);
    try {
      await paymentsApi.updatePolicy(workspaceId, policyDraft);
      await load();
    } finally {
      setSavingPolicy(false);
    }
  };

  const toggleEmergencyStop = async () => {
    if (!policy) return;
    setSavingPolicy(true);
    try {
      await paymentsApi.updatePolicy(workspaceId, { emergencyStop: !policy.emergencyStop });
      await load();
    } finally {
      setSavingPolicy(false);
    }
  };

  const pendingApproval = actions.filter(a => a.policyDecision?.decision === 'REQUIRES_USER_APPROVAL' && a.status === 'POLICY_CHECK');

  if (loading && !wallet) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading Agent Economy…
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="rounded-2xl border border-slate-200/70 bg-gradient-to-br from-white to-slate-50 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_12px_32px_-16px_rgba(15,23,42,0.12)] p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-brand-600 mb-1.5">
              <Zap size={13} /> Agent Economy
            </div>
            <h2 className="text-[26px] font-semibold text-slate-900 tracking-tight leading-tight">
              Ora's autonomous execution layer for USDC
            </h2>
            <p className="text-sm text-slate-500 mt-1 max-w-xl">
              When a goal needs a capability Ora doesn't have in-house, it discovers a provider, checks
              your spending policy, pays in USDC via Circle, and verifies the result — all inside the
              limits you set below.
            </p>
          </div>
          {policy?.emergencyStop && (
            <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700">
              <ShieldX size={14} /> Emergency stop active — all spending blocked
            </div>
          )}
        </div>
      </div>

      {/* Wallet + spending */}
      <section>
        <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight mb-3">Wallet &amp; Spending</h3>
        {!wallet?.exists ? (
          <div className="flex flex-col items-center justify-center text-center py-12 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
            <Wallet size={22} className="text-slate-400 mb-2" />
            <p className="text-sm font-medium text-slate-600">No agent wallet yet</p>
            <p className="text-xs text-slate-400 mt-1 max-w-xs mb-4">
              Create a Circle-controlled USDC wallet for this workspace so Ora's agents can pay for
              external capabilities.
            </p>
            <button
              onClick={handleCreateWallet}
              disabled={creatingWallet}
              className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white font-medium px-4 py-2 rounded-xl text-sm disabled:opacity-50"
            >
              {creatingWallet ? <Loader2 size={14} className="animate-spin" /> : <Wallet size={14} />}
              Create Agent Wallet
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Balance"
              icon={<Wallet size={13} />}
              value={`${(wallet.balance?.amount ?? 0).toFixed(4)} USDC`}
              sub={wallet.isSimulated ? 'Simulated wallet — no real funds' : wallet.blockchain}
            />
            <StatCard
              label="Wallet address"
              icon={<Wallet size={13} />}
              value={<span className="text-sm font-mono break-all">{(wallet.address || '').slice(0, 10)}…{(wallet.address || '').slice(-6)}</span>}
              sub={<button onClick={() => navigator.clipboard.writeText(wallet.address || '')} className="inline-flex items-center gap-1 hover:text-brand-600"><Copy size={11} /> Copy full address</button>}
            />
            <StatCard
              label="Spent today"
              icon={<Zap size={13} />}
              value={fmtUsdc(spending?.today_usdc)}
              sub={spending?.daily_limit_usdc != null ? `of ${fmtUsdc(spending.daily_limit_usdc)} daily limit` : 'no daily limit set'}
            />
            <StatCard
              label="Spent this month"
              icon={<Zap size={13} />}
              value={fmtUsdc(spending?.month_usdc)}
              sub={spending?.monthly_limit_usdc != null ? `of ${fmtUsdc(spending.monthly_limit_usdc)} monthly limit` : 'no monthly limit set'}
            />
          </div>
        )}
      </section>

      {/* Pending approval */}
      {pendingApproval.length > 0 && (
        <section>
          <h3 className="text-[13px] font-semibold text-amber-700 tracking-tight mb-3 flex items-center gap-1.5">
            <ShieldAlert size={14} /> Waiting on your approval
          </h3>
          <div className="space-y-2">
            {pendingApproval.map(a => (
              <div key={a.id} className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">
                    {a.capability} — {fmtUsdc(a.amountUsdc)} to {a.provider?.name || 'unknown provider'}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">{a.reason || a.task}</p>
                  <p className="text-[11px] text-amber-700 mt-1">{a.policyDecision?.reasons?.[0]}</p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleReject(a.id)}
                    disabled={busyActionId === a.id}
                    className="inline-flex items-center gap-1.5 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
                  >
                    <XCircle size={13} /> Reject
                  </button>
                  <button
                    onClick={() => handleApprove(a.id)}
                    disabled={busyActionId === a.id}
                    className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
                  >
                    {busyActionId === a.id ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                    Approve
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Autonomous activity */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight">Autonomous Activity</h3>
          <span className="text-[11px] text-slate-400">{actions.length} purchase{actions.length === 1 ? '' : 's'}</span>
        </div>
        {actions.length === 0 ? (
          <div className="text-center py-10 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50 text-sm text-slate-400">
            Ora hasn't purchased any capabilities yet.
          </div>
        ) : (
          <div className="rounded-2xl border border-slate-200/70 bg-white divide-y divide-slate-100 overflow-hidden">
            {actions.map(a => {
              const style = STATUS_STYLE[a.status] || STATUS_STYLE.PROPOSED;
              return (
                <div key={a.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                      <p className="text-sm font-medium text-slate-800 truncate">{a.capability}</p>
                      <span className={`text-[11px] font-semibold ${style.text}`}>{style.label}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{a.reason || a.task}</p>
                    {a.errorMessage && <p className="text-[11px] text-rose-500 mt-0.5">{a.errorMessage}</p>}
                  </div>
                  <div className="flex items-center gap-4 flex-shrink-0 text-right">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{fmtUsdc(a.amountUsdc)}</p>
                      <p className="text-[11px] text-slate-400">{a.provider?.name || '—'}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Transactions */}
      <section>
        <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight mb-3">Transactions</h3>
        {transactions.length === 0 ? (
          <div className="text-center py-10 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50 text-sm text-slate-400">
            No on-chain transactions yet.
          </div>
        ) : (
          <div className="rounded-2xl border border-slate-200/70 bg-white overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
                  <th className="px-4 py-2 font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Chain</th>
                  <th className="px-4 py-2 font-medium">Transaction</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(t => (
                  <tr key={t.id} className="border-b border-slate-50 last:border-0">
                    <td className="px-4 py-2.5 font-medium text-slate-800">{fmtUsdc(t.amountUsdc)}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-semibold ${t.status === 'CONFIRMED' ? 'text-emerald-600' : t.status === 'FAILED' ? 'text-rose-600' : 'text-amber-600'}`}>
                        {t.status}{t.isSimulated ? ' (sim)' : ''}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-500">{t.chain}</td>
                    <td className="px-4 py-2.5">
                      {t.explorerUrl ? (
                        <a href={t.explorerUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline text-xs">
                          {t.transactionHash?.slice(0, 10)}… <ExternalLink size={11} />
                        </a>
                      ) : <span className="text-xs text-slate-400">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Capabilities marketplace + manual test trigger */}
      <section>
        <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight mb-3 flex items-center gap-1.5">
          <Store size={14} /> Available Capabilities
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-slate-200/70 bg-white divide-y divide-slate-100 overflow-hidden">
            {capabilities.map(c => (
              <div key={c.id} className="p-3.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{c.name}</p>
                  <p className="text-xs text-slate-400 truncate">{c.capability} · {c.provider}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-semibold text-slate-800">{fmtUsdc(c.priceUsdc)}</p>
                  <p className="text-[11px] text-slate-400">{(c.successRate * 100).toFixed(0)}% success</p>
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={handleRunTest} className="rounded-2xl border border-slate-200/70 bg-white p-4 space-y-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <PlayCircle size={14} /> Try an autonomous purchase
            </div>
            <select
              value={testForm.capability}
              onChange={e => setTestForm(f => ({ ...f, capability: e.target.value }))}
              className="w-full text-sm bg-white border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30"
            >
              <option value="">Select a capability…</option>
              {[...new Set(capabilities.map(c => c.capability))].map(cap => (
                <option key={cap} value={cap}>{cap}</option>
              ))}
            </select>
            <input
              value={testForm.task}
              onChange={e => setTestForm(f => ({ ...f, task: e.target.value }))}
              placeholder="Describe the task, e.g. 'research my top 3 competitors'"
              className="w-full text-sm bg-white border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30"
            />
            <button
              type="submit"
              disabled={testBusy || !testForm.capability || !testForm.task}
              className="w-full inline-flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50"
            >
              {testBusy ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              Acquire capability
            </button>
            {testResult && (
              <p className={`text-xs flex items-start gap-1.5 ${testResult.ok ? 'text-emerald-600' : 'text-rose-600'}`}>
                {testResult.ok ? <CheckCircle2 size={13} className="mt-0.5 flex-shrink-0" /> : <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />}
                {testResult.message}
              </p>
            )}
          </form>
        </div>
      </section>

      {/* Policy */}
      <section>
        <h3 className="text-[13px] font-semibold text-slate-600 tracking-tight mb-3 flex items-center gap-1.5">
          <Settings2 size={14} /> Spending Policy
        </h3>
        <div className="rounded-2xl border border-slate-200/70 bg-white p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-slate-500">Per-transaction limit (USDC)</span>
              <input
                type="number" step="0.0001" min="0"
                value={policyDraft?.perTransactionLimitUsdc ?? ''}
                onChange={e => setPolicyDraft(d => d && ({ ...d, perTransactionLimitUsdc: parseFloat(e.target.value) || 0 }))}
                className="mt-1 w-full text-sm bg-white border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">Daily limit (USDC)</span>
              <input
                type="number" step="0.01" min="0"
                value={policyDraft?.dailyLimitUsdc ?? ''}
                onChange={e => setPolicyDraft(d => d && ({ ...d, dailyLimitUsdc: e.target.value === '' ? null : parseFloat(e.target.value) }))}
                className="mt-1 w-full text-sm bg-white border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">Auto-approve threshold (USDC)</span>
              <input
                type="number" step="0.0001" min="0"
                value={policyDraft?.autoApproveThresholdUsdc ?? ''}
                onChange={e => setPolicyDraft(d => d && ({ ...d, autoApproveThresholdUsdc: parseFloat(e.target.value) || 0 }))}
                className="mt-1 w-full text-sm bg-white border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500/30"
              />
            </label>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck size={14} className="text-emerald-500" />
              Purchases at or below the auto-approve threshold execute without asking you first.
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleEmergencyStop}
                disabled={savingPolicy}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border disabled:opacity-50 ${
                  policy?.emergencyStop
                    ? 'bg-rose-600 border-rose-600 text-white hover:bg-rose-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-rose-300 hover:text-rose-600'
                }`}
              >
                <ShieldX size={13} /> {policy?.emergencyStop ? 'Resume spending' : 'Emergency stop'}
              </button>
              <button
                onClick={handleSavePolicy}
                disabled={savingPolicy}
                className="inline-flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
              >
                {savingPolicy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                Save policy
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
