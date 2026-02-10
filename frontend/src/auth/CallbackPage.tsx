import { useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '@/lib/api';
import { hasRoleLevel } from '@/lib/auth';

const REDIRECT_STORAGE_KEY = 'auth.redirectUrl';

interface OnboardingStatus {
  provisioned: boolean;
  tenant_slug: string | null;
  role: string | null;
}

export default function CallbackPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!auth.isAuthenticated || checked) return;

    const token = auth.user?.access_token;
    if (!token) return;

    let cancelled = false;

    async function checkOnboarding() {
      try {
        const resp = await apiFetch('/api/v1/onboarding/status', {}, token);
        if (!resp.ok) {
          // If onboarding check fails, fall through to default redirect
          return null;
        }
        return (await resp.json()) as OnboardingStatus;
      } catch {
        return null;
      }
    }

    async function doRedirect() {
      const status = await checkOnboarding();

      if (cancelled) return;
      setChecked(true);

      // Non-provisioned or viewer users should land on welcome.
      if (status && (!status.provisioned || status.role === 'viewer')) {
        navigate('/welcome', { replace: true });
        return;
      }

      const canAccessConsole = hasRoleLevel(auth.user, 'publisher');

      // If onboarding status is unavailable, avoid routing viewers into a protected dead-end.
      if (!status && !canAccessConsole) {
        navigate('/welcome', { replace: true });
        return;
      }

      // Publisher+ can restore original route or default to console.
      const redirectUrl = sessionStorage.getItem(REDIRECT_STORAGE_KEY);
      sessionStorage.removeItem(REDIRECT_STORAGE_KEY);

      const targetUrl =
        redirectUrl && redirectUrl.startsWith('/') && !redirectUrl.startsWith('//')
          ? redirectUrl
          : '/console';

      navigate(targetUrl, { replace: true });
    }

    void doRedirect();
    return () => { cancelled = true; };
  }, [auth.isAuthenticated, auth.user, auth.user?.access_token, navigate, checked]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-muted-foreground">Completing authentication...</p>
      </div>
    </div>
  );
}
