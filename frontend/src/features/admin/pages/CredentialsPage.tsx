import { useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Award, Plus, ShieldCheck } from 'lucide-react';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { EmptyState } from '@/components/empty-state';
import { LoadingSpinner } from '@/components/loading-spinner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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

interface IssuedCredential {
  id: string;
  dpp_id: string;
  issuer_did: string;
  subject_id: string;
  issuance_date: string;
  expiration_date: string | null;
  revoked: boolean;
  credential: Record<string, unknown>;
  created_at: string;
}

interface DPPSummary {
  id: string;
  status: string;
  asset_ids?: { manufacturerPartId?: string };
}

interface VerifyResult {
  valid: boolean;
  errors: string[];
  issuer_did: string | null;
  subject_id: string | null;
}

async function fetchCredentials(token: string) {
  const res = await tenantApiFetch('/credentials', {}, token);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to load credentials'));
  return res.json() as Promise<IssuedCredential[]>;
}

async function fetchPublishedDPPs(token: string) {
  const res = await tenantApiFetch('/dpps?status=published&limit=200', {}, token);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to load DPPs'));
  return res.json() as Promise<{ dpps: DPPSummary[] }>;
}

async function issueCredential(dppId: string, expirationDays: number, token: string) {
  const res = await tenantApiFetch(`/credentials/issue/${dppId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expiration_days: expirationDays }),
  }, token);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to issue credential'));
  return res.json() as Promise<IssuedCredential>;
}

async function verifyCredential(credential: Record<string, unknown>, token: string) {
  const res = await tenantApiFetch('/credentials/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  }, token);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to verify credential'));
  return res.json() as Promise<VerifyResult>;
}

function statusBadge(cred: IssuedCredential) {
  if (cred.revoked) return <Badge variant="destructive">Revoked</Badge>;
  if (cred.expiration_date && new Date(cred.expiration_date) < new Date()) {
    return <Badge variant="secondary">Expired</Badge>;
  }
  return <Badge variant="default">Valid</Badge>;
}

export default function CredentialsPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const slug = getTenantSlug();

  const [issueOpen, setIssueOpen] = useState(false);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Issue form state
  const [selectedDppId, setSelectedDppId] = useState('');
  const [expirationDays, setExpirationDays] = useState(365);

  // Verify form state
  const [vcJson, setVcJson] = useState('');
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);

  const { data: credentials, isLoading } = useQuery({
    queryKey: ['credentials', slug],
    queryFn: () => fetchCredentials(token ?? ''),
    enabled: !!token,
  });

  const { data: dppsData } = useQuery({
    queryKey: ['published-dpps', slug],
    queryFn: () => fetchPublishedDPPs(token ?? ''),
    enabled: !!token && issueOpen,
  });

  const issueMutation = useMutation({
    mutationFn: () => issueCredential(selectedDppId, expirationDays, token ?? ''),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['credentials'] });
      resetIssueForm();
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const verifyMutation = useMutation({
    mutationFn: (cred: Record<string, unknown>) => verifyCredential(cred, token ?? ''),
    onSuccess: (result) => {
      setVerifyResult(result);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  function resetIssueForm() {
    setIssueOpen(false);
    setSelectedDppId('');
    setExpirationDays(365);
  }

  function resetVerifyForm() {
    setVerifyOpen(false);
    setVcJson('');
    setVerifyResult(null);
  }

  function handleVerify() {
    try {
      const parsed = JSON.parse(vcJson) as Record<string, unknown>;
      verifyMutation.mutate(parsed);
    } catch {
      setError('Invalid JSON');
    }
  }

  if (isLoading) return <LoadingSpinner size="lg" />;

  const publishedDpps = dppsData?.dpps ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Credentials"
        description="Issue and verify W3C Verifiable Credentials for published DPPs"
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setVerifyOpen(true)}>
              <ShieldCheck className="h-4 w-4 mr-2" />
              Verify VC
            </Button>
            <Button onClick={() => setIssueOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Issue VC
            </Button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} showSignIn={false} onSignIn={() => {}} />}

      {!credentials?.length ? (
        <EmptyState
          icon={Award}
          title="No credentials issued"
          description="Issue Verifiable Credentials for your published DPPs to enable trusted data exchange."
        />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>DPP ID</TableHead>
                <TableHead>Issuer DID</TableHead>
                <TableHead>Issued</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead className="text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {credentials.map(cred => (
                <>
                  <TableRow
                    key={cred.id}
                    className="cursor-pointer"
                    onClick={() => setExpandedId(expandedId === cred.id ? null : cred.id)}
                  >
                    <TableCell className="font-mono text-xs">
                      {cred.dpp_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">
                      {cred.issuer_did.slice(0, 30)}...
                    </TableCell>
                    <TableCell className="text-sm">
                      {new Date(cred.issuance_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-sm">
                      {cred.expiration_date
                        ? new Date(cred.expiration_date).toLocaleDateString()
                        : '—'}
                    </TableCell>
                    <TableCell className="text-center">{statusBadge(cred)}</TableCell>
                  </TableRow>
                  {expandedId === cred.id && (
                    <TableRow key={`${cred.id}-detail`}>
                      <TableCell colSpan={5}>
                        <pre className="bg-muted p-4 rounded-md text-xs overflow-auto max-h-80">
                          {JSON.stringify(cred.credential, null, 2)}
                        </pre>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Issue Dialog */}
      <Dialog open={issueOpen} onOpenChange={(open) => { if (!open) resetIssueForm(); else setIssueOpen(true); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Issue Verifiable Credential</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="vc-dpp">Published DPP</Label>
              <Select value={selectedDppId} onValueChange={setSelectedDppId}>
                <SelectTrigger id="vc-dpp">
                  <SelectValue placeholder="Select a published DPP" />
                </SelectTrigger>
                <SelectContent>
                  {publishedDpps.map(dpp => (
                    <SelectItem key={dpp.id} value={dpp.id}>
                      {dpp.asset_ids?.manufacturerPartId || dpp.id.slice(0, 8)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="vc-expiration">Expiration (days)</Label>
              <Input
                id="vc-expiration"
                type="number"
                min={1}
                max={3650}
                value={expirationDays}
                onChange={e => setExpirationDays(Number(e.target.value))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={resetIssueForm}>Cancel</Button>
            <Button
              onClick={() => { void issueMutation.mutateAsync(); }}
              disabled={!selectedDppId || issueMutation.isPending}
            >
              {issueMutation.isPending ? 'Issuing...' : 'Issue Credential'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Verify Dialog */}
      <Dialog open={verifyOpen} onOpenChange={(open) => { if (!open) resetVerifyForm(); else setVerifyOpen(true); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Verify Credential</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="vc-json">Credential JSON</Label>
              <Textarea
                id="vc-json"
                rows={10}
                className="font-mono text-xs"
                placeholder="Paste Verifiable Credential JSON here..."
                value={vcJson}
                onChange={e => setVcJson(e.target.value)}
              />
            </div>
            {verifyResult && (
              <div className="rounded-md border p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge variant={verifyResult.valid ? 'default' : 'destructive'}>
                    {verifyResult.valid ? 'Valid' : 'Invalid'}
                  </Badge>
                </div>
                {verifyResult.issuer_did && (
                  <p className="text-xs text-muted-foreground">
                    Issuer: <span className="font-mono">{verifyResult.issuer_did}</span>
                  </p>
                )}
                {verifyResult.errors.length > 0 && (
                  <ul className="text-xs text-destructive list-disc pl-4">
                    {verifyResult.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={resetVerifyForm}>Close</Button>
            <Button
              onClick={handleVerify}
              disabled={!vcJson.trim() || verifyMutation.isPending}
            >
              {verifyMutation.isPending ? 'Verifying...' : 'Verify'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
