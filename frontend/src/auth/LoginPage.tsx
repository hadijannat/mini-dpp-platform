import { useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import { Navigate, useLocation } from 'react-router-dom';
import { LoadingSpinner } from '@/components/loading-spinner';

export default function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const fromState = (location.state as any)?.from;
  const from =
    fromState?.pathname || fromState?.search || fromState?.hash
      ? `${fromState?.pathname ?? ''}${fromState?.search ?? ''}${fromState?.hash ?? ''}`
      : '/console';

  useEffect(() => {
    if (!auth.isAuthenticated && !auth.isLoading && !auth.activeNavigator) {
      auth.signinRedirect();
    }
  }, [auth]);

  if (auth.isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}
