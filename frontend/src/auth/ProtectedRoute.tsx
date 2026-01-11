import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'viewer' | 'publisher' | 'tenant_admin' | 'admin';
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const auth = useAuth();
  const location = useLocation();

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role if required
  if (requiredRole) {
    const userRoles = (auth.user?.profile as any)?.realm_access?.roles || [];
    const roleHierarchy: Record<string, string[]> = {
      viewer: ['viewer', 'publisher', 'tenant_admin', 'admin'],
      publisher: ['publisher', 'tenant_admin', 'admin'],
      tenant_admin: ['tenant_admin', 'admin'],
      admin: ['admin'],
    };
    const allowed = roleHierarchy[requiredRole] || [requiredRole];
    const hasRole = allowed.some((role) => userRoles.includes(role));

    if (!hasRole) {
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
  }

  return <>{children}</>;
}
