import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import {
  CheckCircle,
  Home,
  Loader2,
  LogOut,
  MailCheck,
  RefreshCcw,
  ShieldAlert,
  UserPlus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import RoleRequestCard from '../components/RoleRequestCard';

interface OnboardingStatus {
  provisioned: boolean;
  tenant_slug: string | null;
  role: string | null;
  email_verified: boolean;
  blockers: string[];
  next_actions: string[];
}

interface ResendVerificationResponse {
  queued: boolean;
  cooldown_seconds: number;
  next_allowed_at: string | null;
}

interface ApiErrorPayload {
  code: string | null;
  message: string;
  cooldownSeconds: number | null;
  nextAllowedAt: string | null;
  retryAfterSeconds: number | null;
}

function normalizeStatus(data: Partial<OnboardingStatus>): OnboardingStatus {
  return {
    provisioned: Boolean(data.provisioned),
    tenant_slug: data.tenant_slug ?? null,
    role: data.role ?? null,
    email_verified: Boolean(data.email_verified),
    blockers: Array.isArray(data.blockers) ? data.blockers : [],
    next_actions: Array.isArray(data.next_actions) ? data.next_actions : [],
  };
}

async function parseApiError(response: Response, fallback: string): Promise<ApiErrorPayload> {
  const retryAfterHeader = response.headers.get('Retry-After');
  const retryAfterSeconds = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : Number.NaN;
  const parsedRetryAfter =
    Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0 ? retryAfterSeconds : null;

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      const body = (await response.json()) as {
        detail?:
          | string
          | {
              code?: string;
              message?: string;
              cooldown_seconds?: number;
              next_allowed_at?: string;
            };
      };
      if (typeof body.detail === 'object' && body.detail) {
        return {
          code: typeof body.detail.code === 'string' ? body.detail.code : null,
          message:
            typeof body.detail.message === 'string' && body.detail.message
              ? body.detail.message
              : fallback,
          cooldownSeconds:
            typeof body.detail.cooldown_seconds === 'number' && body.detail.cooldown_seconds > 0
              ? Math.floor(body.detail.cooldown_seconds)
              : null,
          nextAllowedAt:
            typeof body.detail.next_allowed_at === 'string' ? body.detail.next_allowed_at : null,
          retryAfterSeconds: parsedRetryAfter,
        };
      }
      if (typeof body.detail === 'string' && body.detail) {
        return {
          code: null,
          message: body.detail,
          cooldownSeconds: null,
          nextAllowedAt: null,
          retryAfterSeconds: parsedRetryAfter,
        };
      }
    } catch {
      // Fall back to generic parsing.
    }
  }
  return {
    code: null,
    message: await getApiErrorMessage(response, fallback),
    cooldownSeconds: null,
    nextAllowedAt: null,
    retryAfterSeconds: parsedRetryAfter,
  };
}

export default function WelcomePage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = auth.user?.access_token;

  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [resending, setResending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [resendCooldownRemaining, setResendCooldownRemaining] = useState(0);
  const [resendCooldownWindow, setResendCooldownWindow] = useState(30);

  const refreshStatus = useCallback(
    async (
      mode: 'initial' | 'manual' | 'poll' = 'manual',
      tokenOverride?: string,
    ) => {
      const activeToken = tokenOverride ?? token;
      if (!activeToken) {
        if (mode === 'initial') {
          setLoading(false);
        }
        return;
      }

      if (mode === 'initial') {
        setLoading(true);
      }
      if (mode === 'manual') {
        setRefreshing(true);
      }

      try {
        const resp = await apiFetch('/api/v1/onboarding/status', {}, activeToken);
        if (!resp.ok) {
          throw new Error(await getApiErrorMessage(resp, 'Failed to check onboarding status'));
        }

        const data = normalizeStatus((await resp.json()) as OnboardingStatus);
        setStatus(data);

        // If already provisioned with publisher+ role, go straight to console.
        if (data.provisioned && data.role && data.role !== 'viewer') {
          navigate('/console', { replace: true });
          return;
        }

        if (mode !== 'poll') {
          setError(null);
        }
      } catch (err) {
        if (mode !== 'poll') {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (mode === 'initial') {
          setLoading(false);
        }
        if (mode === 'manual') {
          setRefreshing(false);
        }
      }
    },
    [navigate, token],
  );

  useEffect(() => {
    void refreshStatus('initial');
  }, [refreshStatus]);

  useEffect(() => {
    if (!token || !status?.provisioned || status.role !== 'viewer') {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshStatus('poll');
    }, 15000);
    return () => window.clearInterval(timer);
  }, [refreshStatus, status?.provisioned, status?.role, token]);

  useEffect(() => {
    if (resendCooldownRemaining <= 0) {
      return;
    }
    const timer = window.setInterval(() => {
      setResendCooldownRemaining((previous) => (previous <= 1 ? 0 : previous - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldownRemaining]);

  async function handleProvision() {
    if (!token) return;
    setProvisioning(true);
    setError(null);
    setInfo(null);
    try {
      const resp = await apiFetch(
        '/api/v1/onboarding/provision',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        },
        token,
      );

      if (!resp.ok) {
        const parsed = await parseApiError(resp, 'Provisioning failed');
        if (parsed.code === 'onboarding_email_not_verified') {
          setError('Please verify your email first, then refresh access or resend verification.');
          await refreshStatus('poll');
          return;
        }
        throw new Error(parsed.message);
      }

      const data = normalizeStatus((await resp.json()) as OnboardingStatus);
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provisioning failed');
    } finally {
      setProvisioning(false);
    }
  }

  async function handleRefreshAccess() {
    setError(null);
    setInfo(null);

    let effectiveToken = token;
    try {
      if (typeof auth.signinSilent === 'function') {
        const refreshedUser = await auth.signinSilent();
        effectiveToken = refreshedUser?.access_token ?? effectiveToken;
      }
    } catch {
      setInfo('Session refresh failed. If your role was changed, sign out and sign in again.');
    }

    await refreshStatus('manual', effectiveToken);
  }

  async function handleResendVerification() {
    if (!token || resendCooldownRemaining > 0) return;
    setResending(true);
    setError(null);
    setInfo(null);
    try {
      const resp = await apiFetch(
        '/api/v1/onboarding/resend-verification',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        },
        token,
      );
      if (!resp.ok) {
        const parsed = await parseApiError(resp, 'Failed to resend verification email');
        if (parsed.code === 'verification_resend_cooldown') {
          const retryAfter =
            parsed.cooldownSeconds ?? parsed.retryAfterSeconds ?? resendCooldownWindow;
          setResendCooldownRemaining(retryAfter);
          setInfo(`Please wait ${retryAfter} seconds before requesting another verification email.`);
          return;
        }
        throw new Error(parsed.message);
      }
      const payload = (await resp.json()) as Partial<ResendVerificationResponse>;
      const cooldownSeconds =
        typeof payload.cooldown_seconds === 'number' && payload.cooldown_seconds > 0
          ? Math.floor(payload.cooldown_seconds)
          : resendCooldownWindow;
      setResendCooldownWindow(cooldownSeconds);
      setResendCooldownRemaining(cooldownSeconds);
      setInfo(
        'Verification email sent. Please check your inbox and spam folder. ' +
          `You can resend again in ${cooldownSeconds} seconds.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend verification email');
    } finally {
      setResending(false);
    }
  }

  const blockers = status?.blockers ?? [];
  const hasEmailBlocker = blockers.includes('email_unverified');
  const canProvision = status?.next_actions.includes('provision') ?? false;
  const canRequestRoleUpgrade = status?.next_actions.includes('request_role_upgrade') ?? false;
  const insufficientRoleReason = searchParams.get('reason') === 'insufficient_role';

  const description = useMemo(() => {
    if (status?.provisioned) {
      return "You've been added to the platform. Here's your current access level.";
    }
    if (hasEmailBlocker) {
      return 'Verify your email to continue onboarding and join the default tenant.';
    }
    return 'Get started by joining the platform as a viewer.';
  }, [hasEmailBlocker, status?.provisioned]);

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
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Welcome to DPP Platform</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {insufficientRoleReason && (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                Your current role cannot access the publisher console. You can continue here.
              </div>
            )}

            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {info && (
              <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
                {info}
              </div>
            )}

            {!status?.provisioned && hasEmailBlocker && (
              <div className="space-y-3 rounded-md border p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <ShieldAlert className="h-4 w-4 text-amber-600" />
                  Email verification required
                </div>
                <p className="text-sm text-muted-foreground">
                  We cannot complete onboarding until your email address is verified.
                </p>
                <Button
                  onClick={handleResendVerification}
                  disabled={resending || resendCooldownRemaining > 0}
                  variant="outline"
                  className="w-full"
                >
                  {resending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <MailCheck className="mr-2 h-4 w-4" />
                  )}
                  {resending
                    ? 'Sending verification email...'
                    : resendCooldownRemaining > 0
                      ? `Resend available in ${resendCooldownRemaining}s`
                      : 'Resend verification email'}
                </Button>
                <p className="text-xs text-muted-foreground">
                  You can resend every ~{resendCooldownWindow} seconds.
                </p>
              </div>
            )}

            {!status?.provisioned && canProvision && (
              <Button onClick={handleProvision} disabled={provisioning} className="w-full" size="lg">
                {provisioning ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <UserPlus className="mr-2 h-4 w-4" />
                )}
                Get Started
              </Button>
            )}

            {status?.provisioned && (
              <div className="flex items-center gap-3 rounded-md border p-4">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    You&apos;re a <span className="capitalize">{status.role}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">Tenant: {status.tenant_slug}</p>
                </div>
              </div>
            )}

            {status?.provisioned && status.role === 'viewer' && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  void handleRefreshAccess();
                }}
                disabled={refreshing}
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCcw className="mr-2 h-4 w-4" />
                )}
                Refresh access
              </Button>
            )}

            {status?.provisioned && status.role && status.role !== 'viewer' && (
              <Button variant="outline" className="w-full" onClick={() => navigate('/console')}>
                Go to Console
              </Button>
            )}
          </CardContent>
        </Card>

        {status?.provisioned && canRequestRoleUpgrade && (
          <RoleRequestCard tenantSlug={status.tenant_slug ?? 'default'} />
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Button variant="outline" onClick={() => navigate('/')}>
            <Home className="mr-2 h-4 w-4" />
            Go Home
          </Button>
          <Button variant="ghost" onClick={() => void auth.signoutRedirect()}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  );
}
