import React, { useState } from 'react';
import { Lock, Mail, Loader2, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { login as loginRequest, register as registerRequest, forgotPassword, oauthLoginUrl } from '../../api/auth';
import { AuthShell, GoogleIcon, MicrosoftIcon, authInputClass, authPrimaryButtonClass, authOAuthButtonClass } from './AuthShell';

type Mode = 'login' | 'register' | 'forgot';

const OAuthButton: React.FC<{ provider: 'google' | 'microsoft'; label: string }> = ({ provider, label }) => (
  <a href={oauthLoginUrl(provider)} className={authOAuthButtonClass}>
    {provider === 'google' ? <GoogleIcon /> : <MicrosoftIcon />}
    {label}
  </a>
);

export const LoginScreen: React.FC = () => {
  const { login } = useAuth();

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const resetFeedback = () => { setError(''); setMessage(''); };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFeedback();
    setLoading(true);
    try {
      const { token, user } = await loginRequest(email, password);
      await login(token, user);
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFeedback();
    setLoading(true);
    try {
      const { token, user } = await registerRequest(email, password, name.trim() || undefined);
      await login(token, user);
      // App.tsx gates unverified users into the verification screen automatically.
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Could not create your account.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    resetFeedback();
    setLoading(true);
    try {
      await forgotPassword(email);
      setMessage('If that email has an account, a reset link is on its way.');
    } catch {
      setMessage('If that email has an account, a reset link is on its way.');
    } finally {
      setLoading(false);
    }
  };

  const titles: Record<Mode, string> = {
    login: 'Welcome back',
    register: 'Create your account',
    forgot: 'Reset your password',
  };
  const subtitles: Record<Mode, string> = {
    login: 'Sign in to continue to Ora',
    register: 'Get started with Ora, free',
    forgot: "We'll email you a reset link",
  };

  return (
    <AuthShell title={titles[mode]} subtitle={subtitles[mode]}>
      {mode !== 'forgot' && (
        <div className="space-y-2.5 mb-6">
          <OAuthButton provider="google" label="Continue with Google" />
          <OAuthButton provider="microsoft" label="Continue with Microsoft" />
          <div className="flex items-center gap-3 pt-1">
            <div className="h-px flex-1 bg-slate-200" />
            <span className="text-[11px] uppercase tracking-wider text-slate-400">or</span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>
        </div>
      )}

      <form onSubmit={mode === 'login' ? handleLogin : mode === 'register' ? handleRegister : handleForgot} className="space-y-4">
        {mode === 'register' && (
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Name</label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <input
                type="text" value={name} onChange={(e) => setName(e.target.value)}
                className={authInputClass}
                placeholder="Jane Doe"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">Email</label>
          <div className="relative">
            <Mail className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className={authInputClass}
              placeholder="you@example.com" autoFocus required
            />
          </div>
        </div>

        {mode !== 'forgot' && (
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className={authInputClass}
                placeholder="••••••••" minLength={8} required
              />
            </div>
            {mode === 'login' && (
              <button type="button" onClick={() => { setMode('forgot'); resetFeedback(); }}
                className="mt-2 text-xs text-slate-500 hover:text-brand-600">
                Forgot password?
              </button>
            )}
          </div>
        )}

        {error && <p className="text-xs text-red-600">{error}</p>}
        {message && <p className="text-xs text-emerald-600">{message}</p>}

        <button type="submit" disabled={loading} className={authPrimaryButtonClass}>
          {loading ? <Loader2 className="animate-spin w-4 h-4" /> :
            mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : 'Send reset link'}
        </button>

        {mode === 'forgot' ? (
          <button type="button" onClick={() => { setMode('login'); resetFeedback(); }} className="w-full text-xs text-slate-500 hover:text-brand-600">
            Back to sign in
          </button>
        ) : (
          <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); resetFeedback(); }}
            className="w-full text-xs text-slate-500 hover:text-brand-600">
            {mode === 'login' ? "Don't have an account? Create one" : 'Already have an account? Sign in'}
          </button>
        )}
      </form>
    </AuthShell>
  );
};
