import React, { useState } from 'react';
import { Lock, ArrowRight, ShieldCheck, Fingerprint, Loader2, Mail } from 'lucide-react';
import { requestOtp, verifyOtp, findUserByEmail } from '../services/db';

interface LoginScreenProps {
  onLogin: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin }) => {
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
        await requestOtp(email);
        setStep('otp');
    } catch (err) {
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
        const { token, user } = await verifyOtp(email, otp);
        if (token) {
            localStorage.setItem('sindhai_auth_token', token);
            localStorage.setItem('sindhai_user_id', user.id);
            onLogin();
        }
    } catch (err) {
        setError('Invalid code. Access Denied.');
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

      <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl border border-slate-700 rounded-2xl shadow-2xl p-8 z-10 animate-in fade-in zoom-in-95 duration-500">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-slate-900 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-slate-700 shadow-inner">
            <Fingerprint className="w-8 h-8 text-blue-500" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Sindhai AI</h1>
          <p className="text-slate-400 text-sm mt-2">Secure Enterprise Access</p>
        </div>

        {step === 'email' ? (
            <form onSubmit={handleEmailSubmit} className="space-y-4">
                <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Email Identity</label>
                    <div className="relative group">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Mail className="h-4 w-4 text-slate-500" />
                        </div>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="block w-full pl-10 pr-3 py-3 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all sm:text-sm"
                            placeholder="user@enterprise.com"
                            autoFocus
                            required
                        />
                    </div>
                </div>
                {error && <p className="text-xs text-red-400">{error}</p>}
                <button type="submit" disabled={loading} className="w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-all shadow-lg shadow-blue-900/20 flex justify-center">
                    {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Request Access Code'}
                </button>
            </form>
        ) : (
            <form onSubmit={handleOtpSubmit} className="space-y-4">
                <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Security Token</label>
                    <div className="relative group">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <Lock className="h-4 w-4 text-slate-500" />
                        </div>
                        <input
                            type="text"
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            className="block w-full pl-10 pr-3 py-3 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none font-mono tracking-widest text-center text-lg"
                            placeholder="000000"
                            maxLength={6}
                            autoFocus
                            required
                        />
                    </div>
                </div>
                {error && (
                    <p className="mt-2 text-xs text-red-400 flex items-center gap-1 animate-in slide-in-from-left-2">
                        <ShieldCheck className="w-3 h-3" /> {error}
                    </p>
                )}
                <button type="submit" disabled={loading} className="w-full py-3 px-4 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-all flex justify-center">
                    {loading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Authenticate Session'}
                </button>
                <button type="button" onClick={() => setStep('email')} className="w-full text-xs text-slate-500 hover:text-slate-300">
                    Cancel
                </button>
            </form>
        )}

        <div className="mt-8 text-center">
          <p className="text-xs text-slate-600">
            End-to-End Encrypted &bull; Authorized Personnel Only
          </p>
        </div>
      </div>
    </div>
  );
};
