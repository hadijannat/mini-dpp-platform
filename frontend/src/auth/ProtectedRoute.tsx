import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { hasRoleLevel } from '@/lib/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'viewer' | 'publisher' | 'tenant_admin' | 'admin';
}

function allowsViewerConsoleReadOnly(pathname: string): boolean {
  return /^\/console\/dpps\/[^/]+$/.test(pathname);
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const auth = useAuth();
  const location = useLocation();

  if (!auth.isAuthenticated) {
    // Store the intended destination for post-login redirect
    if (location.pathname !== '/login' && location.pathname !== '/callback') {
      sessionStorage.setItem('auth.redirectUrl', location.pathname + location.search);
    }
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // Check role if required (extracts from both realm and client roles)
  if (requiredRole && !hasRoleLevel(auth.user, requiredRole)) {
    if (requiredRole !== 'viewer' && hasRoleLevel(auth.user, 'viewer')) {
      if (requiredRole === 'publisher' && allowsViewerConsoleReadOnly(location.pathname)) {
        return <>{children}</>;
      }
      const params = new URLSearchParams({
        reason: 'insufficient_role',
        next: `${location.pathname}${location.search}`,
      });
      return <Navigate to={`/welcome?${params.toString()}`} replace />;
    }
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600">Access Denied</h1>
          <p className="mt-2 text-gray-600">
            You need the "{requiredRole}" role to access this page.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
