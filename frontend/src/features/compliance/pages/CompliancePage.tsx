import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle,
  XCircle,
  Search,
} from 'lucide-react';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ComplianceViolation {
  rule_id: string;
  severity: string;
  message: string;
  field_path?: string;
}

interface ComplianceSummary {
  total_rules: number;
  passed: number;
  critical_violations: number;
  warnings: number;
  info?: number;
}

interface ComplianceCheckResult {
  dpp_id: string;
  category: string;
  is_compliant: boolean;
  checked_at: string;
  violations: ComplianceViolation[];
  summary: ComplianceSummary;
}

interface CategoryRuleset {
  category: string;
  description?: string;
  rules: Array<{
    id: string;
    severity: string;
    description: string;
    field?: string;
  }>;
}

interface AllRulesResponse {
  categories: string[];
  rulesets: Record<string, CategoryRuleset>;
}

async function fetchRules(token?: string) {
  const response = await tenantApiFetch('/compliance/rules', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch rules'));
  }
  return response.json() as Promise<AllRulesResponse>;
}

async function checkCompliance(dppId: string, category: string | null, token?: string) {
  const params = category ? `?category=${encodeURIComponent(category)}` : '';
  const response = await tenantApiFetch(`/compliance/check/${dppId}${params}`, {
    method: 'POST',
  }, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Compliance check failed'));
  }
  return response.json() as Promise<ComplianceCheckResult>;
}

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case 'critical':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'info':
      return <Info className="h-4 w-4 text-blue-500" />;
    default:
      return <Info className="h-4 w-4 text-muted-foreground" />;
  }
}

function SeverityBadge({ severity }: { severity: string }) {
  const variant = severity === 'critical' ? 'destructive' : 'secondary';
  return <Badge variant={variant}>{severity}</Badge>;
}

export default function CompliancePage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const [dppId, setDppId] = useState('');
  const [category, setCategory] = useState<string | null>(null);

  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['compliance-rules', tenantSlug],
    queryFn: () => fetchRules(token),
    enabled: Boolean(token),
  });

  const checkMutation = useMutation({
    mutationFn: () => checkCompliance(dppId.trim(), category, token),
  });

  const result = checkMutation.data;
  const pageError = checkMutation.error as Error | undefined;
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const handleCheck = (e: React.FormEvent) => {
    e.preventDefault();
    if (dppId.trim()) {
      checkMutation.mutate();
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="ESPR Compliance"
        description="Check Digital Product Passports against EU sustainability regulations"
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Check form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run Compliance Check</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCheck} className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="dpp-id">DPP ID</Label>
              <Input
                id="dpp-id"
                type="text"
                value={dppId}
                onChange={(e) => setDppId(e.target.value)}
                placeholder="Enter DPP UUID"
                required
              />
            </div>
            <div className="w-48 space-y-2">
              <Label>Category (optional)</Label>
              <Select
                value={category ?? 'auto'}
                onValueChange={(v) => setCategory(v === 'auto' ? null : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Auto-detect" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto-detect</SelectItem>
                  {rulesData?.categories.map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat.charAt(0).toUpperCase() + cat.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={checkMutation.isPending || !dppId.trim()}>
              {checkMutation.isPending ? (
                <LoadingSpinner size="sm" />
              ) : (
                <Search className="h-4 w-4 mr-2" />
              )}
              Check
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="flex items-center gap-3 pt-6">
                {result.is_compliant ? (
                  <ShieldCheck className="h-8 w-8 text-green-500" />
                ) : (
                  <ShieldAlert className="h-8 w-8 text-red-500" />
                )}
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <p className="text-lg font-semibold">
                    {result.is_compliant ? 'Compliant' : 'Non-Compliant'}
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 pt-6">
                <CheckCircle className="h-8 w-8 text-green-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Rules Passed</p>
                  <p className="text-lg font-semibold">
                    {result.summary.passed} / {result.summary.total_rules}
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 pt-6">
                <XCircle className="h-8 w-8 text-red-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Critical</p>
                  <p className="text-lg font-semibold">{result.summary.critical_violations}</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 pt-6">
                <AlertTriangle className="h-8 w-8 text-yellow-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Warnings</p>
                  <p className="text-lg font-semibold">{result.summary.warnings}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Category & timestamp */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Category: <strong className="text-foreground">{result.category}</strong></span>
            <span>Checked: {new Date(result.checked_at).toLocaleString()}</span>
          </div>

          {/* Violations table */}
          {result.violations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Violations ({result.violations.length})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"></TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Field</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.violations.map((v, i) => (
                      <TableRow key={`${v.rule_id}-${i}`}>
                        <TableCell><SeverityIcon severity={v.severity} /></TableCell>
                        <TableCell className="font-mono text-sm">{v.rule_id}</TableCell>
                        <TableCell><SeverityBadge severity={v.severity} /></TableCell>
                        <TableCell>{v.message}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {v.field_path || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Available rules reference */}
      {rulesLoading ? (
        <LoadingSpinner />
      ) : rulesData && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Available Rule Categories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {rulesData.categories.map((cat) => {
                const ruleset = rulesData.rulesets[cat];
                const ruleCount = ruleset?.rules?.length ?? 0;
                return (
                  <Badge key={cat} variant="outline" className="text-sm">
                    {cat.charAt(0).toUpperCase() + cat.slice(1)} ({ruleCount} rules)
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
