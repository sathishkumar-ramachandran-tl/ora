import React, { useState } from 'react';
import { Lock, Mail, Fingerprint, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { authApi } from '../../api/auth';
import { useNavigate } from 'react-router-dom';

export const LoginScreen: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<'email' | 'otp'>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
        await authApi.requestOtp(email);
        setStep('otp');
    } catch (err: any) {
        setError('Failed to send code. Please check email or try again.');
    } finally {
        setLoading(false);
    }
  };

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
        const { token, user } = await authApi.verifyOtp(email, otp);
        await login(token, user);
        // Navigation handled by App.tsx observing user state
    } catch (err: any) {
        setError('Invalid code or expired session.');
    } finally {
        setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl"></div>
      </div>

      <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl border border-slate-700 rounded-2xl shadow-2xl p-8 z-10">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-slate-900 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-slate-700 shadow-inner">
            <Fingerprint className="w-8 h-8 text-blue-500" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Sindhai Cortex</h1>
          <p className="text-slate-400 text-sm mt-2">Enterprise Access</p>
        </div>

        {step === 'email' ? (
            <form onSubmit={handleEmailSubmit} className="space-y-4">
                <div>
                     <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Email Identity</label>
                    <div className="relative">
                        <Mail className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="block w-full pl-10 pr-3 py-3 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                            placeholder="user@enterprise.com"
                            autoFocus
                            required
                        />
                    </div>
                </div>
                {error && <p className="text-xs text-red-400">{error}</p>}
                <button type="submit" disabled={loading} className="w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-all flex justify-center">
                    {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Request Access Code'}
                </button>
            </form>
        ) : (
            <form onSubmit={handleOtpSubmit} className="space-y-4">
                <div>
                   <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Security Token</label>
                    <div className="relative">
                        <Lock className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                        <input
                            type="text"
                            inputMode="numeric"
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            className="block w-full pl-10 pr-3 py-3 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:border-blue-500 outline-none font-mono tracking-widest text-center text-lg"
                            placeholder="000000"
                            autoFocus
                            required
                        />
                    </div>
                </div>
                {error && <p className="text-xs text-red-400">{error}</p>}
                <button type="submit" disabled={loading} className="w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-all flex justify-center">
                    {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Authenticate Session'}
                </button>
                <button type="button" onClick={() => setStep('email')} className="w-full text-xs text-slate-500 hover:text-slate-300">
                    Go Back
                </button>
            </form>
        )}
      </div>
    </div>
  );
};
