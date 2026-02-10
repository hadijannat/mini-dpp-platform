import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { CheckCircle, UserPlus, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import RoleRequestCard from '../components/RoleRequestCard';

interface OnboardingStatus {
  provisioned: boolean;
  tenant_slug: string | null;
  role: string | null;
}

export default function WelcomePage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const token = auth.user?.access_token;

  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function checkStatus() {
      try {
        const resp = await apiFetch('/api/v1/onboarding/status', {}, token);
        if (!resp.ok) throw new Error(await getApiErrorMessage(resp, 'Failed to check status'));
        const data = (await resp.json()) as OnboardingStatus;
        if (!cancelled) {
          setStatus(data);
          // If already provisioned with publisher+ role, go straight to console
          if (data.provisioned && data.role && data.role !== 'viewer') {
            navigate('/console', { replace: true });
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void checkStatus();
    return () => { cancelled = true; };
  }, [token, navigate]);

  async function handleProvision() {
    if (!token) return;
    setProvisioning(true);
    setError(null);
    try {
      const resp = await apiFetch('/api/v1/onboarding/provision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }, token);
      if (!resp.ok) throw new Error(await getApiErrorMessage(resp, 'Provisioning failed'));
      const data = (await resp.json()) as OnboardingStatus;
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provisioning failed');
    } finally {
      setProvisioning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-lg space-y-6">
        {/* Welcome card */}
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Welcome to DPP Platform</CardTitle>
            <CardDescription>
              {status?.provisioned
                ? "You've been added to the platform. Here's your current access level."
                : 'Get started by joining the platform as a viewer.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {!status?.provisioned ? (
              <Button
                onClick={handleProvision}
                disabled={provisioning}
                className="w-full"
                size="lg"
              >
                {provisioning ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <UserPlus className="mr-2 h-4 w-4" />
                )}
                Get Started
              </Button>
            ) : (
              <div className="flex items-center gap-3 rounded-md border p-4">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <div>
                  <p className="text-sm font-medium">
                    You&apos;re a <span className="capitalize">{status.role}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Tenant: {status.tenant_slug}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Role request card (only show after provisioning) */}
        {status?.provisioned && status.role === 'viewer' && (
          <RoleRequestCard tenantSlug={status.tenant_slug ?? 'default'} />
        )}

        {/* Link to console for publisher+ */}
        {status?.provisioned && status.role && status.role !== 'viewer' && (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => navigate('/console')}
          >
            Go to Console
          </Button>
        )}
      </div>
    </div>
  );
}
