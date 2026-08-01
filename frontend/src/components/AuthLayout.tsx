import React, { useState } from 'react';
import { User, Workspace, Persona } from '../types';
import { Shield, Briefcase, GraduationCap, Building2, UserCircle, PenTool, Globe, Mail, ArrowRight, Loader2, MessageSquare, MapPin, Globe as GlobeIcon, FileText, AlertCircle } from 'lucide-react';
import { findUserByEmail, createUser, createWorkspace, getUserWorkspaces, requestOtp, verifyOtp } from '../services/db';
import { trackEvent, identifyUser } from '../services/analytics';

interface AuthLayoutProps {
  onAuthenticated: (user: User, workspace: Workspace) => void;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({ onAuthenticated }) => {
  const [step, setStep] = useState<'email' | 'otp' | 'profile' | 'workspace_select' | 'persona' | 'enterprise_details'>('email');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  
  // Data State
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  // Profile Data
  const [name, setName] = useState('');
  const [gender, setGender] = useState('');
  const [phone, setPhone] = useState('');
  const [age, setAge] = useState('');
  const [location, setLocation] = useState('');

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [userWorkspaces, setUserWorkspaces] = useState<Workspace[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<Persona>('general');
  const [workspaceType, setWorkspaceType] = useState<'personal' | 'enterprise'>('personal');

  const [entDetails, setEntDetails] = useState({
      website: '',
      location: '',
      employees: '1-10',
      category: '',
      description: ''
  });

  // 1. Email Entry
  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    trackEvent('AUTH_SIGNUP_START', { email });

    try {
        await requestOtp(email);
        setStep('otp');
    } catch (e) {
        setError("Could not send verification code. Please try again.");
    } finally {
        setLoading(false);
    }
  };

  // 2. OTP Verification
  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
        const { token, user } = await verifyOtp(email, otp);
        if (token) {
            localStorage.setItem('sindhai_auth_token', token);
            localStorage.setItem('sindhai_user_id', user.id);
            identifyUser(user.id, { email: user.email });
            
            // Check if user exists fully in system or needs profile
            const existingUser = await findUserByEmail(email);
            
            if (existingUser && existingUser.name) {
                setCurrentUser(existingUser);
                const workspaces = await getUserWorkspaces(existingUser.id);
                if (workspaces.length > 0) {
                    setUserWorkspaces(workspaces);
                    setStep('workspace_select');
                } else {
                    setName(existingUser.name);
                    setStep('persona');
                }
            } else {
                setStep('profile');
            }
        }
    } catch (e) {
        setError('Invalid code. Please try again.');
    } finally {
        setLoading(false);
    }
  };

  // ... (Rest of the Profile/Workspace creation flow remains the same as it uses the refactored DB services)
  
  // 3. Profile Completion (New Users)
  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    if (currentUser) {
         setStep('persona');
         setLoading(false);
         return;
    }

    const newUser: User = {
        id: localStorage.getItem('sindhai_user_id') || crypto.randomUUID(), 
        email,
        name,
        avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random`,
        gender,
        phone, 
        age: parseInt(age) || undefined,
        location,
        is_onboarded: true
    };
    
    try {
        await createUser(newUser);
        identifyUser(newUser.id, { email: newUser.email, name: newUser.name });
        trackEvent('AUTH_SIGNUP_COMPLETE');
        setCurrentUser(newUser);
        setStep('persona'); 
    } catch (e) {
        console.error(e);
        setError("Failed to create profile.");
    } finally {
        setLoading(false);
    }
  };

  // 4. Pre-Creation Logic
  const handleWorkspaceConfigNext = () => {
      setError('');
      if (workspaceType === 'enterprise') {
          setStep('enterprise_details');
      } else {
          executeCreateWorkspace();
      }
  };

  // 5. Final Workspace Creation
  const executeCreateWorkspace = async () => {
    if (!currentUser) {
        setError("Session lost. Please sign in again.");
        return;
    }
    setLoading(true);

    const wsName = workspaceType === 'personal' 
        ? `${currentUser.name.split(' ')[0]}'s Sindhai` 
        : `${entDetails.website || currentUser.name + "'s Corp"}`;
    
    const newWorkspace: Workspace = {
        id: crypto.randomUUID(),
        name: wsName,
        type: workspaceType,
        persona: selectedPersona,
        members: [{ userId: currentUser.id, roleId: 'owner', joinedAt: new Date() }],
        customRoles: [],
        companyWebsite: entDetails.website,
        location: entDetails.location,
        employeeCount: entDetails.employees,
        category: entDetails.category,
        aiContextDescription: entDetails.description
    };

    try {
        await createWorkspace(newWorkspace, currentUser.id);
        trackEvent('PROJECT_CREATED', { type: 'workspace', workspaceType });
        onAuthenticated(currentUser, newWorkspace);
    } catch (e) {
        console.error(e);
        setError("Failed to initialize workspace.");
    } finally {
        setLoading(false);
    }
  };

  const handleSelectWorkspace = (ws: Workspace) => {
      if (currentUser) {
          trackEvent('AUTH_LOGIN', { workspaceId: ws.id });
          onAuthenticated(currentUser, ws);
      }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 relative">
      
      {/* Brand Side */}
      <div className="hidden lg:flex w-5/12 bg-slate-900 text-white p-12 flex-col justify-between relative overflow-hidden">
         <div className="absolute inset-0 bg-[linear-gradient(to_bottom_right,#0f172a,#1e293b)]"></div>
         <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
         <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>
         
         <div className="z-10 relative">
             <div className="flex items-center gap-3 mb-8">
                <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
                    <Shield className="w-6 h-6 text-white" />
                </div>
                <span className="text-2xl font-bold tracking-tight">Sindhai</span>
             </div>
             <h1 className="text-4xl font-bold tracking-tight mb-6 leading-tight">
                 Architect your ambition. <br/>
                 <span className="text-indigo-400">Execute with Intelligence.</span>
             </h1>
             <p className="text-slate-400 text-lg max-w-sm leading-relaxed">
                 From PhD thesis defense to Enterprise IPOs. The adaptive operating system that grows with your cognitive load.
             </p>
         </div>
      </div>

      {/* Logic Side */}
      <div className="w-full lg:w-7/12 flex items-center justify-center p-8 bg-white relative">
        <div className="w-full max-w-md">
            
            {step === 'email' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="mb-8">
                        <h2 className="text-2xl font-bold text-slate-900">Welcome to Sindhai</h2>
                        <p className="text-slate-500 mt-2">Log in or Sign up with your email.</p>
                    </div>
                    <form onSubmit={handleEmailSubmit} className="space-y-4">
                        <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">Email Address</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
                                <input 
                                    type="email" 
                                    value={email} 
                                    onChange={e => setEmail(e.target.value)} 
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" 
                                    placeholder="name@company.com"
                                    required autoFocus
                                />
                            </div>
                        </div>
                        {error && <p className="text-sm text-red-500 bg-red-50 p-2 rounded-lg">{error}</p>}
                        <button type="submit" disabled={loading} className="w-full bg-slate-900 text-white py-3 rounded-xl font-medium hover:bg-slate-800 transition-colors flex items-center justify-center gap-2">
                            {loading ? <Loader2 className="animate-spin w-5 h-5" /> : <>Continue <ArrowRight className="w-4 h-4" /></>}
                        </button>
                    </form>
                </div>
            )}

            {step === 'otp' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="mb-8">
                        <h2 className="text-2xl font-bold text-slate-900">Check your inbox</h2>
                        <p className="text-slate-500 mt-2">Enter the code sent to {email}.</p>
                    </div>
                    <form onSubmit={handleOtpSubmit} className="space-y-4">
                         <div className="space-y-1">
                            <input 
                                type="text" 
                                value={otp} 
                                onChange={e => setOtp(e.target.value)} 
                                className="w-full pl-4 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-mono tracking-widest text-lg text-center" 
                                placeholder="123456"
                                maxLength={6}
                                required autoFocus
                            />
                        </div>
                        {error && <p className="text-sm text-red-500 bg-red-50 p-2 rounded-lg">{error}</p>}
                        <button type="submit" disabled={loading} className="w-full bg-slate-900 text-white py-3 rounded-xl font-medium hover:bg-slate-800 transition-colors flex items-center justify-center gap-2">
                            {loading ? <Loader2 className="animate-spin w-5 h-5" /> : 'Verify Access'}
                        </button>
                    </form>
                </div>
            )}

            {/* Profile, Workspace Select, Persona, Enterprise Details steps follow standard format ... */}
            {/* Keeping the rendering logic for these identical to original file, just using the updated state handlers */}
            {step === 'profile' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                     <div className="mb-8">
                        <h2 className="text-2xl font-bold text-slate-900">Setup Profile</h2>
                        <p className="text-slate-500 mt-2">How should we address you?</p>
                    </div>
                    <form onSubmit={handleProfileSubmit} className="space-y-4">
                        <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">Full Name</label>
                            <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" required autoFocus />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                             <div className="space-y-1">
                                <label className="text-sm font-medium text-slate-700">Gender</label>
                                <select value={gender} onChange={e => setGender(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" required>
                                    <option value="">Select</option>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium text-slate-700">Age</label>
                                <input type="number" value={age} onChange={e => setAge(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" required />
                            </div>
                        </div>

                        <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">Phone</label>
                            <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" required />
                        </div>

                        <div className="space-y-1">
                            <label className="text-sm font-medium text-slate-700">Location</label>
                            <input type="text" value={location} onChange={e => setLocation(e.target.value)} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" placeholder="City, Country" required />
                        </div>

                        {error && <p className="text-sm text-red-500 bg-red-50 p-2 rounded-lg">{error}</p>}
                        <button type="submit" disabled={loading} className="w-full bg-indigo-600 text-white py-3 rounded-xl font-medium hover:bg-indigo-700 transition-colors">
                            {loading ? <Loader2 className="animate-spin w-5 h-5" /> : 'Create Profile'}
                        </button>
                    </form>
                </div>
            )}
            
            {step === 'workspace_select' && (
                 <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="mb-8">
                        <h2 className="text-2xl font-bold text-slate-900">Select Workspace</h2>
                        <p className="text-slate-500 mt-2">Pick up where you left off.</p>
                    </div>
                    <div className="space-y-3 mb-6">
                        {userWorkspaces.map(ws => (
                            <button key={ws.id} onClick={() => handleSelectWorkspace(ws)} className="w-full text-left p-4 rounded-xl border border-slate-200 hover:border-indigo-500 hover:bg-indigo-50/50 transition-all flex items-center justify-between group">
                                <div><h3 className="font-semibold text-slate-800">{ws.name}</h3><p className="text-xs text-slate-500 uppercase tracking-wider mt-1">{ws.type}</p></div>
                                <ArrowRight className="w-5 h-5 text-slate-300 group-hover:text-indigo-600" />
                            </button>
                        ))}
                    </div>
                    <button onClick={() => setStep('persona')} className="flex items-center gap-2 text-indigo-600 font-medium hover:underline text-sm">
                        <Briefcase className="w-4 h-4" /> Create new workspace
                    </button>
                 </div>
            )}

            {step === 'persona' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                     <div className="mb-6"><h2 className="text-xl font-bold text-slate-900">Configure Workspace</h2><p className="text-slate-500 text-sm mt-1">Select your operating mode.</p></div>
                     <div className="space-y-6">
                         <div className="grid grid-cols-2 gap-3">
                             <button onClick={() => setWorkspaceType('personal')} className={`p-3 rounded-xl border text-center text-sm font-medium transition-all ${workspaceType === 'personal' ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600'}`}>Personal</button>
                             <button onClick={() => setWorkspaceType('enterprise')} className={`p-3 rounded-xl border text-center text-sm font-medium transition-all ${workspaceType === 'enterprise' ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600'}`}>Enterprise</button>
                         </div>
                        <div className="space-y-2">
                             <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Select Persona</label>
                             <div className="grid grid-cols-1 gap-2 max-h-[300px] overflow-y-auto custom-scrollbar border border-slate-100 rounded-xl p-2 bg-slate-50">
                                {[{ id: 'general', icon: UserCircle, label: 'General Executive' }, { id: 'student_mit', icon: GraduationCap, label: 'Elite Student' }, { id: 'phd_researcher', icon: GraduationCap, label: 'PhD Researcher' }, { id: 'software_engineer', icon: Briefcase, label: 'Tech Founder' }, { id: 'politician', icon: Building2, label: 'Public Leader' }, { id: 'upsc_aspirant', icon: PenTool, label: 'Civil Services' }, { id: 'freelancer', icon: Globe, label: 'Freelancer' }].map((p) => (
                                    <button key={p.id} onClick={() => setSelectedPersona(p.id as Persona)} className={`flex items-start gap-3 p-3 rounded-lg border text-left transition-all bg-white ${selectedPersona === p.id ? 'border-indigo-500 ring-1 ring-indigo-500' : 'border-slate-200 hover:border-slate-300'}`}>
                                        <div className={`p-1.5 rounded-md ${selectedPersona === p.id ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-500'}`}><p.icon size={16} /></div>
                                        <div className="font-bold text-sm text-slate-800">{p.label}</div>
                                    </button>
                                ))}
                             </div>
                        </div>
                         {error && (<div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg flex items-center gap-2 animate-in slide-in-from-top-1"><AlertCircle size={16} className="flex-shrink-0" /> {error}</div>)}
                         <button onClick={handleWorkspaceConfigNext} disabled={loading} className="w-full bg-slate-900 text-white py-3 rounded-xl font-medium hover:bg-slate-800 transition-colors flex items-center justify-center gap-2">{loading ? <Loader2 className="animate-spin w-5 h-5" /> : 'Continue'}</button>
                     </div>
                </div>
            )}

            {step === 'enterprise_details' && (
                <div className="animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="mb-6"><h2 className="text-xl font-bold text-slate-900">Organization Details</h2><p className="text-slate-500 text-sm mt-1">Provide context for the AI Strategist.</p></div>
                    <div className="space-y-4 h-[400px] overflow-y-auto custom-scrollbar pr-2">
                        <div><label className="text-xs font-semibold text-slate-500 uppercase">Website / Name</label><div className="relative mt-1"><GlobeIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" /><input type="text" value={entDetails.website} onChange={e => setEntDetails({...entDetails, website: e.target.value})} className="w-full pl-9 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="e.g. Acme Corp" /></div></div>
                        <div className="grid grid-cols-2 gap-3">
                             <div><label className="text-xs font-semibold text-slate-500 uppercase">Location</label><div className="relative mt-1"><MapPin className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" /><input type="text" value={entDetails.location} onChange={e => setEntDetails({...entDetails, location: e.target.value})} className="w-full pl-9 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="City, Country" /></div></div>
                             <div><label className="text-xs font-semibold text-slate-500 uppercase">Size</label><select value={entDetails.employees} onChange={e => setEntDetails({...entDetails, employees: e.target.value})} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"><option>1-10</option><option>11-50</option><option>51-200</option><option>200+</option></select></div>
                        </div>
                        <div><label className="text-xs font-semibold text-slate-500 uppercase">Industry Category</label><div className="relative mt-1"><Building2 className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" /><input type="text" value={entDetails.category} onChange={e => setEntDetails({...entDetails, category: e.target.value})} className="w-full pl-9 px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="e.g. SaaS, Biotech, Retail" /></div></div>
                        <div><label className="text-xs font-semibold text-slate-500 uppercase">AI Context Description</label><div className="relative mt-1"><FileText className="absolute left-3 top-3 text-slate-400 w-4 h-4" /><textarea value={entDetails.description} onChange={e => setEntDetails({...entDetails, description: e.target.value})} className="w-full pl-9 px-3 py-2 border border-slate-200 rounded-lg text-sm" rows={3} placeholder="Tell Sindhai about your company's core value proposition and goals..." /></div></div>
                        {error && (<div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg flex items-center gap-2 animate-in slide-in-from-top-1"><AlertCircle size={16} className="flex-shrink-0" /> {error}</div>)}
                        <button onClick={executeCreateWorkspace} disabled={loading} className="w-full bg-slate-900 text-white py-3 rounded-xl font-medium hover:bg-slate-800 transition-colors flex items-center justify-center gap-2">{loading ? <Loader2 className="animate-spin w-5 h-5" /> : 'Initialize Enterprise'}</button>
                    </div>
                </div>
            )}
        </div>
      </div>
    </div>
  );
};
