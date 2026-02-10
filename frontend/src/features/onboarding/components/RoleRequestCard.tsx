import { useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { ArrowUpCircle, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';

interface RoleRequest {
  id: string;
  requested_role: string;
  status: string;
  reason: string | null;
  review_note: string | null;
  created_at: string;
}

interface RoleRequestCardProps {
  tenantSlug: string;
}

const statusConfig: Record<string, { icon: typeof Clock; variant: 'default' | 'secondary' | 'destructive'; label: string }> = {
  pending: { icon: Clock, variant: 'default', label: 'Pending' },
  approved: { icon: CheckCircle, variant: 'secondary', label: 'Approved' },
  denied: { icon: XCircle, variant: 'destructive', label: 'Denied' },
};

export default function RoleRequestCard({ tenantSlug }: RoleRequestCardProps) {
  const auth = useAuth();
  const token = auth.user?.access_token;

  const [requests, setRequests] = useState<RoleRequest[]>([]);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function load() {
      try {
        const resp = await tenantApiFetch('/role-requests/mine', {}, token, tenantSlug);
        if (resp.ok) {
          const data = (await resp.json()) as RoleRequest[];
          if (!cancelled) setRequests(data);
        }
      } catch {
        // Silently ignore — this is a non-critical UI enhancement
      }
    }

    void load();
    return () => { cancelled = true; };
  }, [token, tenantSlug]);

  const hasPending = requests.some((r) => r.status === 'pending');

  async function handleSubmit() {
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      const resp = await tenantApiFetch(
        '/role-requests',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            requested_role: 'publisher',
            reason: reason.trim() || null,
          }),
        },
        token,
        tenantSlug
      );
      if (!resp.ok) throw new Error(await getApiErrorMessage(resp, 'Failed to submit request'));
      const data = (await resp.json()) as RoleRequest;
      setRequests((prev) => [data, ...prev]);
      setReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ArrowUpCircle className="h-5 w-5" />
          Request Publisher Access
        </CardTitle>
        <CardDescription>
          Publisher access lets you create and manage Digital Product Passports.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Existing requests */}
        {requests.length > 0 && (
          <div className="space-y-2">
            {requests.map((req) => {
              const config = statusConfig[req.status] ?? statusConfig.pending;
              const Icon = config.icon;
              return (
                <div key={req.id} className="flex items-center gap-3 rounded-md border p-3">
                  <Icon className="h-4 w-4 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium capitalize">{req.requested_role}</p>
                    {req.review_note && (
                      <p className="text-xs text-muted-foreground truncate">{req.review_note}</p>
                    )}
                  </div>
                  <Badge variant={config.variant}>{config.label}</Badge>
                </div>
              );
            })}
          </div>
        )}

        {/* Submit form (only if no pending request) */}
        {!hasPending && (
          <div className="space-y-3">
            <Textarea
              placeholder="Why do you need publisher access? (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              maxLength={1000}
            />
            <Button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full"
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ArrowUpCircle className="mr-2 h-4 w-4" />
              )}
              Request Publisher Access
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
