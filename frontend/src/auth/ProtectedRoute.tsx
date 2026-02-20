import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { hasRoleLevel } from '@/lib/auth';
import { useTenantAccess } from '@/lib/tenant-access';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'viewer' | 'publisher' | 'tenant_admin' | 'admin';
  roleSource?: 'token' | 'tenant';
}

function allowsViewerConsoleReadOnly(pathname: string): boolean {
  return /^\/console\/dpps\/[^/]+$/.test(pathname);
}

export default function ProtectedRoute({
  children,
  requiredRole,
  roleSource = 'token',
}: ProtectedRouteProps) {
  const auth = useAuth();
  const location = useLocation();
  const tenantAccess = useTenantAccess();

  if (!auth.isAuthenticated) {
    // Store the intended destination for post-login redirect
    if (location.pathname !== '/login' && location.pathname !== '/callback') {
      sessionStorage.setItem('auth.redirectUrl', location.pathname + location.search);
    }
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  const hasRequiredRole =
    requiredRole === undefined
      ? true
      : roleSource === 'tenant'
        ? tenantAccess.hasTenantRoleLevel(requiredRole)
        : hasRoleLevel(auth.user, requiredRole);

  const hasViewerLevelAccess =
    roleSource === 'tenant'
      ? tenantAccess.hasTenantRoleLevel('viewer')
      : hasRoleLevel(auth.user, 'viewer');

  if (requiredRole && roleSource === 'tenant' && tenantAccess.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  // Check role if required.
  if (requiredRole && !hasRequiredRole) {
    if (requiredRole !== 'viewer' && hasViewerLevelAccess) {
      if (requiredRole === 'publisher' && allowsViewerConsoleReadOnly(location.pathname)) {
        return <>{children}</>;
      }
      const params = new URLSearchParams({
        reason: 'insufficient_role',
        next: `${location.pathname}${location.search}`,
      });
      if (roleSource === 'tenant' && tenantAccess.tenantSlug) {
        params.set('tenant', tenantAccess.tenantSlug);
      }
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
