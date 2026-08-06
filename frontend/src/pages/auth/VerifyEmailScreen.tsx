import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { verifyEmailCode, resendVerification } from '../../api/auth';
import { AuthShell, authPrimaryButtonClass } from './AuthShell';

export const VerifyEmailScreen: React.FC = () => {
  const { user, refreshUser, logout } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verifyEmailCode(code);
      await refreshUser();
    } catch {
      setError('Invalid or expired code.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResent(false);
    await resendVerification();
    setResent(true);
  };

  return (
    <AuthShell
      title="Verify your email"
      subtitle={<>We sent a 6-digit code to <span className="text-slate-700 font-medium">{user?.email}</span></>}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)}
          className="block w-full px-3 py-3 bg-white border border-slate-300 rounded-lg text-slate-900
            focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none font-mono tracking-widest text-center text-lg"
          placeholder="000000" autoFocus required
        />
        {error && <p className="text-xs text-red-600 text-center">{error}</p>}
        {resent && <p className="text-xs text-emerald-600 text-center">New code sent.</p>}

        <button type="submit" disabled={loading} className={authPrimaryButtonClass}>
          {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Verify'}
        </button>
        <button type="button" onClick={handleResend} className="w-full text-xs text-slate-500 hover:text-brand-600">
          Resend code
        </button>
        <button type="button" onClick={logout} className="w-full text-xs text-slate-400 hover:text-slate-600">
          Sign out
        </button>
      </form>
    </AuthShell>
  );
};
