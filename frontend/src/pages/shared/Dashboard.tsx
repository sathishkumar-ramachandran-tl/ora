import React from 'react';

export const Dashboard: React.FC = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-4">Dashboard</h1>
      <p className="text-gray-600">Welcome to your dashboard. Select a workspace or project to begin.</p>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="font-semibold text-lg mb-2">My Focus</h3>
          <p className="text-sm text-gray-500">No active tasks for today.</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="font-semibold text-lg mb-2">Recent Activity</h3>
          <p className="text-sm text-gray-500">You logged in just now.</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="font-semibold text-lg mb-2">Projects</h3>
          <p className="text-sm text-gray-500">View your active projects.</p>
        </div>
      </div>
    </div>
  );
};