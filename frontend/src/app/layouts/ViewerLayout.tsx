import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { ArrowLeft, LayoutDashboard, LogIn } from 'lucide-react';
import { isPublisher } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';

export default function ViewerLayout() {
  const navigate = useNavigate();
  const auth = useAuth();
  const isAuthenticated = auth.isAuthenticated;
  const canAccessConsole = isAuthenticated && isPublisher(auth.user);

  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    if (canAccessConsole) {
      navigate('/console/dpps');
      return;
    }
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBack}
              data-testid="viewer-back"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>

            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-foreground">
                Digital Product Passport
              </h1>
              <Badge
                variant="secondary"
                className="border-blue-200 bg-blue-50 text-blue-700"
              >
                EU DPP
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Breadcrumb className="hidden sm:flex">
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage>Digital Product Passport</BreadcrumbPage>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>View</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>

            {canAccessConsole && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/console/dpps')}
                data-testid="viewer-dashboard"
              >
                <LayoutDashboard className="mr-1 h-4 w-4" />
                Dashboard
              </Button>
            )}

            {!isAuthenticated && !auth.isLoading && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/login')}
                data-testid="viewer-sign-in"
              >
                <LogIn className="mr-1 h-4 w-4" />
                Sign in
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
