import { useAuth } from 'react-oidc-context';
import { Navigate, useLocation } from 'react-router-dom';

export default function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const fromState = (location.state as any)?.from;
  const from =
    fromState?.pathname || fromState?.search || fromState?.hash
      ? `${fromState?.pathname ?? ''}${fromState?.search ?? ''}${fromState?.hash ?? ''}`
      : '/console';

  if (auth.isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h1 className="text-3xl font-bold text-center text-gray-900">
            Mini DPP Platform
          </h1>
          <p className="mt-2 text-center text-gray-600">
            Digital Product Passport Management System
          </p>
        </div>

        <button
          onClick={() => auth.signinRedirect()}
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Sign in with Keycloak
        </button>

        {auth.error && (
          <div className="text-red-600 text-sm text-center">
            Error: {auth.error.message}
          </div>
        )}
      </div>
    </div>
  );
}
