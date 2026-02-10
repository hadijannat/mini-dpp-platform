import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Upload, CheckCircle, XCircle } from 'lucide-react';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ActorBadge } from '@/components/actor-badge';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
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

interface BatchImportResultItem {
  index: number;
  dpp_id: string | null;
  status: string;
  error: string | null;
}

interface BatchImportResponse {
  job_id: string;
  total: number;
  succeeded: number;
  failed: number;
  results: BatchImportResultItem[];
}

interface ActorSummary {
  subject: string;
  display_name?: string | null;
  email_masked?: string | null;
}

interface BatchImportJobSummary {
  id: string;
  requested_by_subject: string;
  requested_by: ActorSummary;
  total: number;
  succeeded: number;
  failed: number;
  created_at: string;
}

interface BatchImportJobItem {
  index: number;
  dpp_id: string | null;
  status: string;
  error: string | null;
  created_at: string;
}

interface BatchImportJobDetail extends BatchImportJobSummary {
  items: BatchImportJobItem[];
}

async function fetchBatchJobs(token?: string) {
  const response = await tenantApiFetch('/dpps/batch-import/jobs?limit=50&offset=0', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load batch import history'));
  }
  return response.json() as Promise<{ jobs: BatchImportJobSummary[] }>;
}

async function fetchBatchJobDetail(jobId: string, token?: string) {
  const response = await tenantApiFetch(`/dpps/batch-import/jobs/${jobId}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load batch import details'));
  }
  return response.json() as Promise<BatchImportJobDetail>;
}

export default function BatchImportPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const [jsonInput, setJsonInput] = useState('');
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BatchImportResponse | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const {
    data: jobsData,
    isLoading: jobsLoading,
    isError: jobsError,
    error: jobsErrorObj,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ['batch-import-jobs', tenantSlug],
    queryFn: () => fetchBatchJobs(token),
    enabled: Boolean(token),
  });

  const {
    data: selectedJob,
    isLoading: selectedJobLoading,
  } = useQuery({
    queryKey: ['batch-import-job-detail', tenantSlug, selectedJobId],
    queryFn: () => fetchBatchJobDetail(selectedJobId as string, token),
    enabled: Boolean(token) && Boolean(selectedJobId),
  });

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setJsonInput(ev.target?.result as string);
      setResult(null);
      setError(null);
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!jsonInput.trim() || !token) return;
    setImporting(true);
    setError(null);
    setResult(null);

    try {
      const parsed = JSON.parse(jsonInput);
      const dpps = Array.isArray(parsed) ? parsed : parsed.dpps;
      if (!Array.isArray(dpps)) {
        setError('JSON must be an array of DPP objects or { dpps: [...] }');
        return;
      }

      const response = await tenantApiFetch('/dpps/batch-import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dpps }),
      }, token);

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, 'Batch import failed'));
      }

      const payload = (await response.json()) as BatchImportResponse;
      setResult(payload);
      setSelectedJobId(payload.job_id);
      void refetchJobs();
    } catch (err) {
      setError((err as Error).message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const historyError = jobsError ? (jobsErrorObj as Error)?.message : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Batch Import"
        description="Import multiple DPPs from a JSON file"
      />

      {(error || historyError) && (
        <ErrorBanner
          message={error || historyError || 'Something went wrong.'}
          showSignIn={false}
          onSignIn={() => {}}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upload JSON</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              className="text-sm"
            />
            <span className="text-xs text-muted-foreground">or paste JSON below</span>
          </div>

          <textarea
            value={jsonInput}
            onChange={(e) => { setJsonInput(e.target.value); setResult(null); }}
            placeholder='[{"asset_ids": {"manufacturerPartId": "PART-001"}, "selected_templates": ["digital-nameplate"]}, ...]'
            className="h-48 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />

          <Button
            onClick={() => { void handleImport(); }}
            disabled={!jsonInput.trim() || importing}
          >
            <Upload className="h-4 w-4 mr-2" />
            {importing ? 'Importing...' : 'Import DPPs'}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-3">
              Import Results
              <Badge variant="secondary">{result.succeeded} succeeded</Badge>
              {result.failed > 0 && (
                <Badge variant="destructive">{result.failed} failed</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>DPP ID</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.results.map((r) => (
                <TableRow key={r.index}>
                  <TableCell>{r.index + 1}</TableCell>
                  <TableCell>
                    {r.status === 'ok' ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {r.dpp_id ? r.dpp_id.slice(0, 12) : '-'}
                  </TableCell>
                  <TableCell className="text-xs text-destructive">
                    {r.error || '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Batch Import History</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Started</TableHead>
              <TableHead>Requested By</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Succeeded</TableHead>
              <TableHead>Failed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(jobsData?.jobs ?? []).map((job) => (
              <TableRow
                key={job.id}
                className="cursor-pointer"
                onClick={() => setSelectedJobId(job.id)}
              >
                <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <ActorBadge actor={job.requested_by} fallbackSubject={job.requested_by_subject} />
                </TableCell>
                <TableCell>{job.total}</TableCell>
                <TableCell>{job.succeeded}</TableCell>
                <TableCell>{job.failed}</TableCell>
              </TableRow>
            ))}
            {!jobsLoading && (!jobsData?.jobs || jobsData.jobs.length === 0) && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                  No batch import jobs found yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      {selectedJobId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Job Details {selectedJob ? `(${selectedJob.id.slice(0, 8)})` : ''}
            </CardTitle>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>DPP ID</TableHead>
                <TableHead>Error</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {selectedJobLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                    Loading job details...
                  </TableCell>
                </TableRow>
              )}
              {(selectedJob?.items ?? []).map((item) => (
                <TableRow key={`${selectedJob?.id}-${item.index}`}>
                  <TableCell>{item.index + 1}</TableCell>
                  <TableCell>
                    {item.status === 'ok' ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.dpp_id ? item.dpp_id.slice(0, 12) : '-'}
                  </TableCell>
                  <TableCell className="text-xs text-destructive">{item.error || '-'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
