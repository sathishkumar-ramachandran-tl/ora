import React, { useState } from 'react';
import { User } from '../types';
import { updateProfile } from '../services/db';
import { UserCircle, MapPin, Phone, Calendar, ArrowRight, Loader2 } from 'lucide-react';

interface OnboardingScreenProps {
  user: User;
  onComplete: () => void;
}

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ user, onComplete }) => {
  const [formData, setFormData] = useState({
    name: user.name || '',
    gender: '',
    phone: '',
    age: '',
    location: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.gender || !formData.phone || !formData.age || !formData.location) {
        setError('Please fill in all fields');
        return;
    }

    setLoading(true);
    try {
        await updateProfile({
            ...formData,
            age: parseInt(formData.age)
        });
        onComplete();
    } catch (err) {
        setError("Failed to update profile. Please try again.");
    } finally {
        setLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="w-full max-w-md p-8 bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700">
        <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Welcome to Sindhai</h1>
            <p className="text-slate-500 dark:text-slate-400">Let's verify your identity details.</p>
        </div>

        {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm text-center border border-red-200">
                {error}
            </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Full Name</label>
                <div className="relative">
                    <UserCircle className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                    <input 
                        type="text" 
                        value={formData.name}
                        onChange={e => setFormData({...formData, name: e.target.value})}
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                        placeholder="John Doe"
                    />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div>
                     <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Gender</label>
                     <select 
                        value={formData.gender}
                        onChange={e => setFormData({...formData, gender: e.target.value})}
                        className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                     >
                        <option value="">Select</option>
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                     </select>
                </div>
                <div>
                    <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Age</label>
                    <div className="relative">
                         <Calendar className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                         <input 
                            type="number"
                            value={formData.age}
                            onChange={e => setFormData({...formData, age: e.target.value})}
                            className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                            placeholder="25"
                         />
                    </div>
                </div>
            </div>

            <div>
                <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Phone Number</label>
                <div className="relative">
                    <Phone className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                    <input 
                        type="tel" 
                        value={formData.phone}
                        onChange={e => setFormData({...formData, phone: e.target.value})}
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                        placeholder="+1 (555) 000-0000"
                    />
                </div>
            </div>

             <div>
                <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Location</label>
                <div className="relative">
                    <MapPin className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                    <input 
                        type="text" 
                        value={formData.location}
                        onChange={e => setFormData({...formData, location: e.target.value})}
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                        placeholder="City, Country"
                    />
                </div>
            </div>

            <button 
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg mt-6 flex items-center justify-center transition-all disabled:opacity-50"
            >
                {loading ? <Loader2 className="animate-spin h-5 w-5" /> : (
                    <>
                        Complete Setup <ArrowRight className="ml-2 h-5 w-5" />
                    </>
                )}
            </button>
        </form>
      </div>
    </div>
  );
};
