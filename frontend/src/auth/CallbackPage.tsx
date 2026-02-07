import { useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { useNavigate } from 'react-router-dom';

const REDIRECT_STORAGE_KEY = 'auth.redirectUrl';

export default function CallbackPage() {
  const auth = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (auth.isAuthenticated) {
      // Restore the original route if available
      const redirectUrl = sessionStorage.getItem(REDIRECT_STORAGE_KEY);
      sessionStorage.removeItem(REDIRECT_STORAGE_KEY);

      // Validate the redirect URL is a relative path (prevent open redirect)
      const targetUrl =
        redirectUrl && redirectUrl.startsWith('/') && !redirectUrl.startsWith('//')
          ? redirectUrl
          : '/console';

      navigate(targetUrl, { replace: true });
    }
  }, [auth.isAuthenticated, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-muted-foreground">Completing authentication...</p>
      </div>
    </div>
  );
}
