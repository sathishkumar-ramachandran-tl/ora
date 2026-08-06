import React, { useState } from 'react';
import {
  ArrowRight, ArrowLeft, Loader2, Building2, User,
  Phone, MapPin, GraduationCap, Briefcase, Target, Rocket, Home
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { updateProfile } from '../../api/auth';
import { createWorkspace } from '../../api/workspace';
import { createOrganization } from '../../api/org';
import { Purpose } from '../../types';
import { OraMark, authInputClass } from './AuthShell';

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
      await updateProfile({
        name: name.trim(),
        phone: phone.trim() || undefined,
        age: age ? Number(age) : undefined,
        country: country.trim() || undefined,
        purpose: purpose as Purpose,
        is_onboarded: true,
      } as any);

      // Company workspaces need a real Organization behind them (owns billing, RBAC,
      // and cross-workspace membership) — create it first, then the workspace tied to it.
      const organizationId = wsType === 'company'
        ? (await createOrganization(wsName.trim())).id
        : undefined;
      await createWorkspace(user.id, wsName.trim(), wsType, 'general', organizationId);

      window.location.reload();
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const stepIndex = step === 'profile' ? 0 : step === 'wstype' ? 1 : 2;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex flex-col items-center mb-6">
          <OraMark />
          <span className="mt-3 text-lg font-semibold text-slate-900 tracking-tight">Ora</span>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-6">
          {[0, 1, 2].map(i => (
            <div key={i} className={`h-1 rounded-full transition-all duration-300
              ${i === stepIndex ? 'w-8 bg-brand-600' : i < stepIndex ? 'w-4 bg-brand-300' : 'w-4 bg-slate-200'}`} />
          ))}
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
          {/* Step: Profile */}
          {step === 'profile' && (
            <form onSubmit={handleProfileNext} className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Tell us about yourself</h2>
                <p className="text-slate-500 text-sm mt-1">Your AI will personalize everything around you.</p>
              </div>

              {/* Name */}
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">Full Name *</label>
                <input
                  autoFocus
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  className={authInputClass.replace('pl-10', 'pl-4')}
                />
              </div>

              {/* Phone + Age row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-600 mb-1.5 block">Phone</label>
                  <div className="relative">
                    <Phone size={13} className="absolute left-3 top-3.5 text-slate-400" />
                    <input
                      value={phone}
                      onChange={e => setPhone(e.target.value)}
                      placeholder="+91 9999..."
                      type="tel"
                      className={authInputClass}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 mb-1.5 block">Age</label>
                  <input
                    value={age}
                    onChange={e => setAge(e.target.value)}
                    placeholder="25"
                    type="number"
                    min={10}
                    max={100}
                    className={authInputClass.replace('pl-10', 'pl-4')}
                  />
                </div>
              </div>

              {/* Country */}
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">Country</label>
                <div className="relative">
                  <MapPin size={13} className="absolute left-3 top-3.5 text-slate-400" />
                  <input
                    value={country}
                    onChange={e => setCountry(e.target.value)}
                    placeholder="India, USA, UK…"
                    className={authInputClass}
                  />
                </div>
              </div>

              {/* Purpose */}
              <div>
                <label className="text-xs font-medium text-slate-600 mb-2 block">Primary Purpose *</label>
                <div className="grid grid-cols-2 gap-2">
                  {PURPOSES.map(({ value, label, description, icon: Icon }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setPurpose(value)}
                      className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-all
                        ${purpose === value
                          ? 'border-brand-500 bg-brand-50 text-slate-900'
                          : 'border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700'}`}>
                      <Icon size={16} className={`flex-shrink-0 mt-0.5 ${purpose === value ? 'text-brand-600' : ''}`} />
                      <div>
                        <p className="text-xs font-semibold">{label}</p>
                        <p className="text-[10px] text-slate-400 leading-tight">{description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={!name.trim() || !purpose}
                className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-xl text-sm font-medium transition-colors">
                Continue <ArrowRight size={15} />
              </button>
            </form>
          )}

          {/* Step: Workspace Type */}
          {step === 'wstype' && (
            <div className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Set up your workspace</h2>
                <p className="text-slate-500 text-sm mt-1">How will you primarily use Ora?</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => { setWsType('personal'); setStep('wsname'); }}
                  className="group p-5 border border-slate-200 hover:border-brand-400 rounded-xl text-left transition-all hover:bg-brand-50/50">
                  <div className="w-9 h-9 bg-brand-50 rounded-lg flex items-center justify-center mb-3 group-hover:bg-brand-600 transition-colors">
                    <User size={18} className="text-brand-600 group-hover:text-white" />
                  </div>
                  <p className="text-sm font-semibold text-slate-900 mb-1">Personal</p>
                  <p className="text-xs text-slate-500 leading-snug">For individual goals, learning & freelance</p>
                </button>

                <button
                  onClick={() => { setWsType('company'); setStep('wsname'); }}
                  className="group p-5 border border-slate-200 hover:border-blue-400 rounded-xl text-left transition-all hover:bg-blue-50/50">
                  <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-600 transition-colors">
                    <Building2 size={18} className="text-blue-600 group-hover:text-white" />
                  </div>
                  <p className="text-sm font-semibold text-slate-900 mb-1">Company</p>
                  <p className="text-xs text-slate-500 leading-snug">Team collaboration, RBAC & projects</p>
                </button>
              </div>

              <button onClick={() => setStep('profile')} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 transition-colors">
                <ArrowLeft size={13} /> Back
              </button>
            </div>
          )}

          {/* Step: Workspace Name */}
          {step === 'wsname' && (
            <form onSubmit={handleCreate} className="p-6 space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  {wsType === 'personal' ? 'Name your workspace' : 'Company name'}
                </h2>
                <p className="text-slate-500 text-sm mt-1">You can create more workspaces later.</p>
              </div>

              <input
                autoFocus
                value={wsName}
                onChange={e => setWsName(e.target.value)}
                placeholder={wsType === 'personal' ? 'My Research Hub' : 'Acme Corp'}
                required
                className={authInputClass.replace('pl-10', 'pl-4')}
              />

              {error && <p className="text-xs text-red-600">{error}</p>}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep('wstype')}
                  className="px-4 py-2.5 text-xs text-slate-500 hover:text-slate-800 border border-slate-200 hover:border-slate-300 rounded-xl transition-colors flex items-center gap-1">
                  <ArrowLeft size={13} /> Back
                </button>
                <button
                  type="submit"
                  disabled={loading || !wsName.trim()}
                  className="flex-1 flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-xl text-sm font-medium transition-colors">
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <>Launch Ora <Target size={15} /></>}
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-slate-400 mt-4">
          Logged in as <span className="text-slate-500">{user?.email}</span>
        </p>
      </div>
    </div>
  );
};
