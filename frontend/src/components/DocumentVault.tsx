import React, { useState, useEffect } from 'react';
import { FileText, Upload, FolderOpen, Download, Trash2, Search, HardDrive } from 'lucide-react';
import { Document } from '../types';
import axios from 'axios';
import { API_BASE_URL, getAuthHeader } from '../config';

interface DocumentVaultProps {
  workspaceId: string;
}

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

export const DocumentVault: React.FC<DocumentVaultProps> = ({ workspaceId }) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  const filteredDocuments = documents.filter(doc =>
    doc.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    if (workspaceId) {
      loadDocuments();
    }
  }, [workspaceId]);

  const loadDocuments = async () => {
    try {
      setError(null);
      const headers = getAuthHeader();
      if (!headers.Authorization) {
        setError('Not authenticated');
        return;
      }

      const response = await axios.get(
        `${API_BASE_URL}/workspaces/${workspaceId}/documents`,
        { headers }
      );
      setDocuments(response.data.map((d: any) => ({
        ...d,
        uploadedAt: new Date(d.uploadedAt)
      })));
    } catch (e: any) {
      console.error('Failed to load documents', e);
      setError(e.response?.data?.error || 'Failed to load documents');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setUploading(true);

    try {
      // In production, upload to cloud storage (Firebase, S3, etc)
      // For now, simulate upload and create metadata entry
      const newDoc: Document = {
        id: crypto.randomUUID(),
        name: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date(),
        bucketPath: `sindhai_secure/${workspaceId}/docs/${Date.now()}_${file.name}`,
        tags: ['uploaded']
      };

      // Save metadata to backend
      await axios.post(
        `${API_BASE_URL}/documents`,
        {
          id: newDoc.id,
          workspaceId,
          name: newDoc.name,
          size: newDoc.size,
          type: newDoc.type,
          bucketPath: newDoc.bucketPath,
          tags: newDoc.tags
        },
        { headers: getAuthHeader() }
      );

      setDocuments((prev: Document[]) => [newDoc, ...prev]);
    } catch (e) {
      console.error('Failed to upload document', e);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    try {
      await axios.delete(
        `${API_BASE_URL}/documents/${docId}`,
        { headers: getAuthHeader() }
      );
      setDocuments((prev: Document[]) => prev.filter((d: Document) => d.id !== docId));
    } catch (e) {
      console.error('Failed to delete document', e);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-slate-50">
            <div>
                <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-indigo-600" /> Secure Vault
                </h2>
                <p className="text-xs text-slate-500 font-mono mt-1">Encrypted Storage • {workspaceId.substring(0,8)}</p>
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
                <label className="flex items-center justify-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors cursor-pointer w-full sm:w-auto">
                    {uploading ? 'Encrypting & Uploading...' : <><Upload size={16} /> Upload Securely</>}
                    <input 
                      type="file"
                      onChange={handleFileUpload}
                      disabled={uploading}
                      className="hidden"
                    />
                </label>
            </div>
        </div>
        
        {error && (
          <div className="p-4 bg-red-50 border-b border-red-200 text-red-700 text-sm rounded-none">
            {error}
          </div>
        )}

        <div className="p-4 border-b border-slate-100">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                <input 
                    type="text" 
                    placeholder="Search documents..." 
                    value={searchQuery}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-slate-100 border-transparent focus:bg-white focus:border-indigo-500 border rounded-lg text-sm outline-none transition-all"
                />
            </div>
        </div>

        <div className="flex-1 overflow-auto custom-scrollbar p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredDocuments.map((doc: Document) => (
                    <div key={doc.id} className="group border border-slate-200 rounded-xl p-4 hover:shadow-md transition-shadow bg-white relative">
                        <div className="flex items-start justify-between mb-3">
                            <div className="p-2 bg-slate-100 rounded-lg text-slate-500">
                                <FileText size={24} />
                            </div>
                            <button 
                              onClick={() => handleDeleteDocument(doc.id)}
                              className="text-slate-400 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100">
                                <Trash2 size={16} />
                            </button>
                        </div>
                        <h3 className="font-semibold text-slate-800 text-sm truncate" title={doc.name}>{doc.name}</h3>
                        <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                            <span>{formatSize(doc.size)}</span>
                            <span>•</span>
                            <span>{doc.uploadedAt.toLocaleDateString()}</span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1">
                            {doc.tags.map((tag: string) => (
                                <span key={tag} className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] rounded-full uppercase font-medium">
                                    {tag}
                                </span>
                            ))}
                        </div>
                        <div className="absolute inset-0 bg-white/50 opacity-0 group-hover:opacity-100 flex items-center justify-center backdrop-blur-[1px] transition-opacity rounded-xl">
                            <button className="bg-white text-indigo-600 shadow-lg border border-slate-100 px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transform translate-y-2 group-hover:translate-y-0 transition-transform">
                                <Download size={16} /> Download
                            </button>
                        </div>
                    </div>
                ))}
            </div>
            {filteredDocuments.length === 0 && (
                <div className="text-center py-20 text-slate-400">
                    <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
                    <p>{documents.length === 0 ? 'Vault is empty. Upload documents to seed the Knowledge Graph.' : 'No documents match your search.'}</p>
                </div>
            )}
        </div>
    </div>
  );
};