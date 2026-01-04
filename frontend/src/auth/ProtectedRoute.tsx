import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'viewer' | 'publisher' | 'admin';
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
    const hasRole = userRoles.includes(requiredRole) || userRoles.includes('admin');

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
