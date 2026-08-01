import React, { useState } from 'react';
import {
  ArrowRight, ArrowLeft, Loader2, Building2, User,
  Phone, MapPin, GraduationCap, Briefcase, Target, Rocket, Home, Bot
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import { authApi } from '../../api/auth';
import { Purpose } from '../../types';

type Step = 'profile' | 'wstype' | 'wsname';

const PURPOSES: { value: Purpose; label: string; description: string; icon: React.ElementType }[] = [
  { value: 'learning', label: 'Learning', description: 'Student or researcher', icon: GraduationCap },
  { value: 'freelancing', label: 'Freelancing', description: 'Independent work & clients', icon: Briefcase },
  { value: 'personal', label: 'Personal', description: 'Life management & goals', icon: Home },
  { value: 'startup', label: 'Startup', description: 'Building a product', icon: Rocket },
];

export const Onboarding: React.FC = () => {
  const { user } = useAuth();
  const [step, setStep] = useState<Step>('profile');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Profile fields
  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState('');
  const [age, setAge] = useState('');
  const [country, setCountry] = useState('');
  const [purpose, setPurpose] = useState<Purpose | ''>('');

  // Workspace fields
  const [wsType, setWsType] = useState<'personal' | 'company'>('personal');
  const [wsName, setWsName] = useState('');

  const handleProfileNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !purpose) return;
    setStep('wstype');
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wsName.trim() || !user) return;
    setLoading(true);
    setError('');
    try {
      // Save profile
      await authApi.updateProfile({
        name: name.trim(),
        phone: phone.trim() || undefined,
        age: age ? Number(age) : undefined,
        country: country.trim() || undefined,
        purpose: purpose as Purpose,
        is_onboarded: true,
      } as any);

      // Create workspace
      await apiClient.post('/workspaces', {
        workspace: {
          id: crypto.randomUUID(),
          name: wsName.trim(),
          context: wsType,
          type: wsType === 'personal' ? 'study' : 'project',
          persona: 'general',
        },
        userId: user.id
      });

      window.location.reload();
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const stepIndex = step === 'profile' ? 0 : step === 'wstype' ? 1 : 2;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
      {/* Background glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/4 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/3 w-60 h-60 bg-purple-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-lg relative z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
            <Bot size={20} className="text-white" />
          </div>
          <span className="text-white font-bold text-xl tracking-tight">Sindhai Cortex</span>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-6">
          {[0, 1, 2].map(i => (
            <div key={i} className={`h-1 rounded-full transition-all duration-300
              ${i === stepIndex ? 'w-8 bg-indigo-500' : i < stepIndex ? 'w-4 bg-indigo-700' : 'w-4 bg-slate-700'}`} />
          ))}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
          {/* Step: Profile */}
          {step === 'profile' && (
            <form onSubmit={handleProfileNext} className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-bold text-white">Tell us about yourself</h2>
                <p className="text-slate-400 text-sm mt-1">Your AI will personalize everything around you.</p>
              </div>

              {/* Name */}
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 block">Full Name *</label>
                <input
                  autoFocus
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              {/* Phone + Age row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 block">Phone</label>
                  <div className="relative">
                    <Phone size={13} className="absolute left-3 top-3 text-slate-500" />
                    <input
                      value={phone}
                      onChange={e => setPhone(e.target.value)}
                      placeholder="+91 9999..."
                      type="tel"
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-8 pr-3 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 block">Age</label>
                  <input
                    value={age}
                    onChange={e => setAge(e.target.value)}
                    placeholder="25"
                    type="number"
                    min={10}
                    max={100}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>
              </div>

              {/* Country */}
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 block">Country</label>
                <div className="relative">
                  <MapPin size={13} className="absolute left-3 top-3 text-slate-500" />
                  <input
                    value={country}
                    onChange={e => setCountry(e.target.value)}
                    placeholder="India, USA, UK…"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-8 pr-3 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>
              </div>

              {/* Purpose */}
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 block">Primary Purpose *</label>
                <div className="grid grid-cols-2 gap-2">
                  {PURPOSES.map(({ value, label, description, icon: Icon }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setPurpose(value)}
                      className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-all
                        ${purpose === value
                          ? 'border-indigo-500 bg-indigo-500/10 text-white'
                          : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'}`}>
                      <Icon size={16} className={`flex-shrink-0 mt-0.5 ${purpose === value ? 'text-indigo-400' : ''}`} />
                      <div>
                        <p className="text-xs font-semibold">{label}</p>
                        <p className="text-[10px] text-slate-500 leading-tight">{description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={!name.trim() || !purpose}
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-xl text-sm font-semibold transition-all">
                Continue <ArrowRight size={15} />
              </button>
            </form>
          )}

          {/* Step: Workspace Type */}
          {step === 'wstype' && (
            <div className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-bold text-white">Set up your workspace</h2>
                <p className="text-slate-400 text-sm mt-1">How will you primarily use Sindhai?</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => { setWsType('personal'); setStep('wsname'); }}
                  className="group p-5 border border-slate-700 hover:border-indigo-500 rounded-xl text-left transition-all hover:bg-indigo-500/5">
                  <div className="w-9 h-9 bg-indigo-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-indigo-600 transition-colors">
                    <User size={18} className="text-indigo-400 group-hover:text-white" />
                  </div>
                  <p className="text-sm font-bold text-white mb-1">Personal</p>
                  <p className="text-xs text-slate-500 leading-snug">For individual goals, learning & freelance</p>
                </button>

                <button
                  onClick={() => { setWsType('company'); setStep('wsname'); }}
                  className="group p-5 border border-slate-700 hover:border-blue-500 rounded-xl text-left transition-all hover:bg-blue-500/5">
                  <div className="w-9 h-9 bg-blue-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-600 transition-colors">
                    <Building2 size={18} className="text-blue-400 group-hover:text-white" />
                  </div>
                  <p className="text-sm font-bold text-white mb-1">Company</p>
                  <p className="text-xs text-slate-500 leading-snug">Team collaboration, RBAC & projects</p>
                </button>
              </div>

              <button onClick={() => setStep('profile')} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <ArrowLeft size={13} /> Back
              </button>
            </div>
          )}

          {/* Step: Workspace Name */}
          {step === 'wsname' && (
            <form onSubmit={handleCreate} className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-bold text-white">
                  {wsType === 'personal' ? 'Name your workspace' : 'Company name'}
                </h2>
                <p className="text-slate-400 text-sm mt-1">You can create more workspaces later.</p>
              </div>

              <input
                autoFocus
                value={wsName}
                onChange={e => setWsName(e.target.value)}
                placeholder={wsType === 'personal' ? 'My Research Hub' : 'Acme Corp'}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-colors"
              />

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep('wstype')}
                  className="px-4 py-2.5 text-xs text-slate-400 hover:text-white border border-slate-700 hover:border-slate-600 rounded-xl transition-colors flex items-center gap-1">
                  <ArrowLeft size={13} /> Back
                </button>
                <button
                  type="submit"
                  disabled={loading || !wsName.trim()}
                  className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-xl text-sm font-semibold transition-all">
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <>Launch Cortex <Target size={15} /></>}
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-slate-600 mt-4">
          Logged in as <span className="text-slate-400">{user?.email}</span>
        </p>
      </div>
    </div>
  );
};
