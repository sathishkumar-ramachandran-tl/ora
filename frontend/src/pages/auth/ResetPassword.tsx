import React, { useState } from 'react';
import { Lock, Loader2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { resetPassword } from '../../api/auth';
import { AuthShell, authInputClass, authPrimaryButtonClass } from './AuthShell';

export const ResetPassword: React.FC = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') || '';

  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
      setTimeout(() => navigate('/login', { replace: true }), 2000);
    } catch {
      setError('This reset link is invalid or has expired.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Set a new password">
      {done ? (
        <p className="text-sm text-emerald-600 text-center">Password updated — redirecting you to sign in…</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className={authInputClass}
              placeholder="New password" minLength={8} autoFocus required
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button type="submit" disabled={loading || !token} className={authPrimaryButtonClass}>
            {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Update password'}
          </button>
        </form>
      )}
    </AuthShell>
  );
};
