import React, { useState, useEffect } from 'react';
import { 
    Users, 
    UserPlus, 
    Shield, 
    MoreVertical, 
    Search,
    Mail,
    CheckCircle,
    XCircle,
    Building
} from 'lucide-react';
import { Organization } from '../types';
import { getOrgDashboard, getOrgMembers, inviteMember, OrgMember, updateMemberRole } from '../services/orgService';

interface AdminConsoleProps {
    organization: Organization;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({ organization }) => {
    const [view, setView] = useState<'overview' | 'members'>('overview');
    
    return (
        <div className="flex flex-col h-full bg-slate-50">
            {/* Sub-header Navigation */}
            <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center space-x-6">
                <button 
                    onClick={() => setView('overview')}
                    className={`pb-1 text-sm font-medium border-b-2 transition-colors ${
                        view === 'overview' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                >
                    Overview
                </button>
                <button 
                    onClick={() => setView('members')}
                    className={`pb-1 text-sm font-medium border-b-2 transition-colors ${
                        view === 'members' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                >
                    Members & Access
                </button>
                <div  className={`pb-1 text-sm font-medium text-gray-400 cursor-not-allowed`}>
                    Billing (Coming Soon)
                </div>
                <div  className={`pb-1 text-sm font-medium text-gray-400 cursor-not-allowed`}>
                    Security Policies (Pro)
                </div>
            </div>

            <div className="flex-1 p-6 overflow-auto">
                {view === 'overview' && <OverviewPanel organization={organization} />}
                {view === 'members' && <MemberManagement organization={organization} />}
            </div>
        </div>
    );
};

const OverviewPanel: React.FC<{ organization: Organization }> = ({ organization }) => {
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getOrgDashboard(organization.id).then(data => {
            setStats(data.stats);
            setLoading(false);
        });
    }, [organization.id]);

    if (loading) return <div className="p-4">Loading stats...</div>;

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <h2 className="text-xl font-bold text-gray-800">Organization Overview</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard 
                    icon={<Users className="text-blue-600" />} 
                    label="Total Members" 
                    value={stats?.totalMembers || 0} 
                />
                <StatCard 
                    icon={<Building className="text-indigo-600" />} 
                    label="Active Workspaces" 
                    value={stats?.totalWorkspaces || 0} 
                />
                <StatCard 
                    icon={<CheckCircle className="text-green-600" />} 
                    label="Active Projects" 
                    value={stats?.activeProjects || '-'} 
                />
            </div>
            
            {/* Quick Actions or recent activity can go here */}
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
                <h3 className="text-md font-medium text-gray-700 mb-4">Onboarding Status</h3>
                <div className="flex items-center space-x-3 text-sm text-gray-500">
                    <CheckCircle size={16} className="text-green-500" />
                    <span>Organization Created</span>
                </div>
            </div>
        </div>
    );
};

const MemberManagement: React.FC<{ organization: Organization }> = ({ organization }) => {
    const [members, setMembers] = useState<OrgMember[]>([]);
    const [inviteEmail, setInviteEmail] = useState('');
    const [isInviting, setIsInviting] = useState(false);
    const [showInviteModal, setShowInviteModal] = useState(false);

    useEffect(() => {
        loadMembers();
    }, [organization.id]);

    const loadMembers = async () => {
        const list = await getOrgMembers(organization.id);
        setMembers(list);
    };

    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsInviting(true);
        try {
            await inviteMember(organization.id, inviteEmail, 'member');
            await loadMembers();
            setInviteEmail('');
            setShowInviteModal(false);
        } catch (err) {
            alert("Failed to invite");
        }
        setIsInviting(false);
    };
    
    const changeRole = async (userId: string, newRole: string) => {
        await updateMemberRole(organization.id, userId, newRole);
        loadMembers();
    };

    return (
        <div className="max-w-5xl mx-auto">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-gray-800">Members</h2>
                <button 
                    onClick={() => setShowInviteModal(true)}
                    className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                    <UserPlus size={18} />
                    <span>Invite Member</span>
                </button>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">User</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Role</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Status</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase">Joined</th>
                            <th className="text-right py-3 px-4"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {members.map(member => (
                            <tr key={member.id} className="hover:bg-gray-50">
                                <td className="py-3 px-4">
                                    <div className="flex flex-col">
                                        <span className="font-medium text-gray-800">{member.name || 'Pending...'}</span>
                                        <span className="text-sm text-gray-500">{member.email}</span>
                                    </div>
                                </td>
                                <td className="py-3 px-4">
                                    <select 
                                        value={member.role}
                                        onChange={(e) => changeRole(member.id, e.target.value)}
                                        className="text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                    >
                                        <option value="admin">Admin</option>
                                        <option value="member">Member</option>
                                        <option value="owner">Owner</option>
                                    </select>
                                </td>
                                <td className="py-3 px-4">
                                    <StatusBadge status={member.status} />
                                </td>
                                <td className="py-3 px-4 text-sm text-gray-500">
                                    {new Date(member.joinedAt).toLocaleDateString()}
                                </td>
                                <td className="py-3 px-4 text-right">
                                    <button className="text-gray-400 hover:text-gray-600">
                                        <MoreVertical size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            
            {showInviteModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-6 w-96">
                        <h3 className="text-lg font-bold mb-4">Invite Team Member</h3>
                        <form onSubmit={handleInvite}>
                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                <div className="flex items-center border rounded-lg px-3 py-2">
                                    <Mail size={16} className="text-gray-400 mr-2" />
                                    <input 
                                        type="email" 
                                        required
                                        className="flex-1 outline-none text-sm"
                                        placeholder="colleague@company.com"
                                        value={inviteEmail}
                                        onChange={(e) => setInviteEmail(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="flex justify-end space-x-2">
                                <button 
                                    type="button" 
                                    onClick={() => setShowInviteModal(false)}
                                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button 
                                    type="submit" 
                                    disabled={isInviting}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                                >
                                    {isInviting ? 'Sending...' : 'Send Invite'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: number | string }> = ({ icon, label, value }) => (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center space-x-4">
        <div className="p-3 bg-gray-50 rounded-full">
            {icon}
        </div>
        <div>
            <div className="text-2xl font-bold text-gray-800">{value}</div>
            <div className="text-sm text-gray-500">{label}</div>
        </div>
    </div>
);

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const styles = {
        active: 'bg-green-100 text-green-800',
        invited: 'bg-yellow-100 text-yellow-800',
        suspended: 'bg-red-100 text-red-800'
    };
    
    // @ts-ignore
    const style = styles[status] || 'bg-gray-100 text-gray-800';
    
    return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${style}`}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
    );
};
