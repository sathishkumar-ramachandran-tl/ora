import React, { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { getCurrentUser } from '../../api/auth';
import { AuthShell } from './AuthShell';

/** Landing page for /auth/oauth/<provider>/callback's redirect — captures the JWT
 * from the query string and completes the same login() flow as password sign-in. */
export const OAuthCallback: React.FC = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const token = params.get('token');
    const error = params.get('error');
    if (error) {
      navigate('/login?error=oauth_failed', { replace: true });
      return;
    }
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }
    localStorage.setItem('ora_auth_token', token);
    getCurrentUser()
      .then((user) => login(token, user))
      .catch(() => navigate('/login', { replace: true }))
      .finally(() => navigate('/', { replace: true }));
  }, []);

  return (
    <AuthShell title="Signing you in…">
      <div className="flex justify-center py-2">
        <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
      </div>
    </AuthShell>
  );
};
