import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { FileText, Send, FileEdit, FileCode, Plus, ArrowRight } from 'lucide-react';
import { apiFetch, getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { PageHeader } from '@/components/page-header';
import { StatusBadge } from '@/components/status-badge';
import { ErrorBanner } from '@/components/error-banner';
import { EmptyState } from '@/components/empty-state';

async function fetchDPPs(token?: string) {
  const response = await tenantApiFetch('/dpps', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPPs'));
  }
  return response.json();
}

async function fetchTemplates(token?: string) {
  const response = await apiFetch('/api/v1/templates', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch templates'));
  }
  return response.json();
}

const statIcons = [FileText, Send, FileEdit, FileCode] as const;

export default function DashboardPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const token = auth.user?.access_token;
  const tenantSlug = getTenantSlug();

  const { data: dpps, isError: dppsError, error: dppsErrorObj } = useQuery({
    queryKey: ['dpps', tenantSlug],
    queryFn: () => fetchDPPs(token),
    enabled: Boolean(token),
  });

  const { data: templates, isError: templatesError, error: templatesErrorObj } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(token),
    enabled: Boolean(token),
  });

  const pageError =
    (dppsError ? (dppsErrorObj as Error) : null) ??
    (templatesError ? (templatesErrorObj as Error) : null);
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const stats = [
    { name: 'Total DPPs', value: dpps?.count || 0 },
    { name: 'Published', value: dpps?.dpps?.filter((d: any) => d.status === 'published').length || 0 },
    { name: 'Drafts', value: dpps?.dpps?.filter((d: any) => d.status === 'draft').length || 0 },
    { name: 'Templates', value: templates?.count || 0 },
  ];

  const quickActions = [
    {
      title: 'Create DPP',
      description: 'Create a new Digital Product Passport',
      icon: Plus,
      to: '/console/dpps',
    },
    {
      title: 'View Templates',
      description: 'Browse available DPP4.0 templates',
      icon: FileText,
      to: '/console/templates',
    },
    {
      title: 'Manage Connectors',
      description: 'Configure Catena-X integrations',
      icon: FileText,
      to: '/console/connectors',
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="Overview of your Digital Product Passports"
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, index) => {
          const Icon = statIcons[index];
          return (
            <Card key={stat.name}>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="rounded-lg bg-primary/10 p-3">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{stat.name}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {quickActions.map((action) => (
            <Card key={action.title} className="transition-colors hover:bg-accent/50">
              <CardContent className="flex items-center gap-4 p-4">
                <action.icon className="h-8 w-8 text-primary" />
                <div className="flex-1">
                  <h3 className="text-sm font-medium">{action.title}</h3>
                  <p className="text-sm text-muted-foreground">{action.description}</p>
                </div>
                <Button variant="ghost" size="sm" asChild>
                  <Link to={action.to}>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Recent DPPs */}
      {dpps?.dpps?.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Recent DPPs</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dpps.dpps.slice(0, 5).map((dpp: any) => (
                  <TableRow
                    key={dpp.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/console/dpps/${dpp.id}`)}
                  >
                    <TableCell className="font-medium">
                      {dpp.asset_ids?.manufacturerPartId || dpp.id}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={dpp.status} />
                    </TableCell>
                    <TableCell>
                      {new Date(dpp.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={FileText}
              title="No DPPs yet"
              description="Create your first Digital Product Passport"
              action={
                <Button asChild>
                  <Link to="/console/dpps">Create DPP</Link>
                </Button>
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
