import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  Building2,
  FileText,
  Users,
  Activity,
  Send,
  ScrollText,
} from 'lucide-react';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface TenantMetrics {
  tenant_id: string;
  slug: string;
  name: string;
  status: string;
  total_dpps: number;
  draft_dpps: number;
  published_dpps: number;
  archived_dpps: number;
  total_revisions: number;
  total_members: number;
  total_epcis_events: number;
  total_audit_events: number;
}

interface PlatformMetricsResponse {
  tenants: TenantMetrics[];
  totals: {
    total_tenants: number;
    total_dpps: number;
    total_published: number;
    total_members: number;
    total_epcis_events: number;
    total_audit_events: number;
  };
}

async function fetchMetrics(token?: string): Promise<PlatformMetricsResponse> {
  const response = await apiFetch('/api/v1/tenants/metrics/platform', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch metrics'));
  }
  return response.json();
}

export default function AdminDashboardPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin-metrics'],
    queryFn: () => fetchMetrics(token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  });

  const pageError = isError ? (error as Error) : undefined;
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  if (isLoading) return <LoadingSpinner />;

  const totals = data?.totals;

  const overviewCards = [
    { label: 'Tenants', value: totals?.total_tenants ?? 0, icon: Building2 },
    { label: 'Total DPPs', value: totals?.total_dpps ?? 0, icon: FileText },
    { label: 'Published', value: totals?.total_published ?? 0, icon: Send },
    { label: 'Members', value: totals?.total_members ?? 0, icon: Users },
    { label: 'EPCIS Events', value: totals?.total_epcis_events ?? 0, icon: Activity },
    { label: 'Audit Events', value: totals?.total_audit_events ?? 0, icon: ScrollText },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin Dashboard"
        description="Platform-wide usage metrics and tenant overview"
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Overview cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {overviewCards.map((card) => (
          <Card key={card.label}>
            <CardContent className="flex flex-col items-center gap-2 p-4 text-center">
              <div className="rounded-lg bg-primary/10 p-2">
                <card.icon className="h-5 w-5 text-primary" />
              </div>
              <p className="text-2xl font-bold">{card.value}</p>
              <p className="text-xs text-muted-foreground">{card.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Per-tenant table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Per-Tenant Breakdown</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tenant</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">DPPs</TableHead>
              <TableHead className="text-right">Published</TableHead>
              <TableHead className="text-right">Revisions</TableHead>
              <TableHead className="text-right">Members</TableHead>
              <TableHead className="text-right">EPCIS</TableHead>
              <TableHead className="text-right">Audit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.tenants.map((t) => (
              <TableRow key={t.tenant_id}>
                <TableCell>
                  <div>
                    <span className="font-medium">{t.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground font-mono">
                      {t.slug}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={t.status === 'active' ? 'secondary' : 'outline'}
                    className={
                      t.status === 'active'
                        ? 'bg-green-100 text-green-800'
                        : ''
                    }
                  >
                    {t.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.total_dpps}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.published_dpps}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.total_revisions}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.total_members}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.total_epcis_events}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {t.total_audit_events}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data?.tenants.length === 0 && (
          <div className="p-8 text-center text-muted-foreground">
            No tenants found.
          </div>
        )}
      </Card>
    </div>
  );
}
