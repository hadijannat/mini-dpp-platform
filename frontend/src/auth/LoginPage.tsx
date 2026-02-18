import { useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { LoadingSpinner } from '@/components/loading-spinner';

export default function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const registrationMode = searchParams.get('mode') === 'register';
  const fromState = (location.state as any)?.from;
  const from =
    fromState?.pathname || fromState?.search || fromState?.hash
      ? `${fromState?.pathname ?? ''}${fromState?.search ?? ''}${fromState?.hash ?? ''}`
      : '/console';

  useEffect(() => {
    if (!auth.isAuthenticated && !auth.isLoading && !auth.activeNavigator) {
      if (registrationMode) {
        auth.signinRedirect({ extraQueryParams: { kc_action: 'register' } });
      } else {
        auth.signinRedirect();
      }
    }
  }, [auth, registrationMode]);

  if (auth.isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}
