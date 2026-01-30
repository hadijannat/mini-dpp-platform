import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { ArrowLeft, LayoutDashboard } from 'lucide-react';
import { isPublisher } from '@/lib/auth';

export default function ViewerLayout() {
  const navigate = useNavigate();
  const auth = useAuth();
  const canAccessConsole = isPublisher(auth.user);

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    if (canAccessConsole) {
      navigate('/console/dpps');
      return;
    }
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
              data-testid="viewer-back"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back
            </button>
            <h1 className="text-xl font-semibold text-gray-900">
              Digital Product Passport
            </h1>
          </div>
          {canAccessConsole && (
            <button
              type="button"
              onClick={() => navigate('/console/dpps')}
              className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
              data-testid="viewer-dashboard"
            >
              <LayoutDashboard className="h-4 w-4 mr-1" />
              Dashboard
            </button>
          )}
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
