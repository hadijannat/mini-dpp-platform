import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, GitCompareArrows } from 'lucide-react';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/loading-spinner';
import { DiffViewer } from './DiffViewer';

type Revision = {
  id: string;
  revision_no: number;
  state: string;
  digest_sha256: string;
  created_by_subject: string;
  created_at: string;
};

type DiffEntry = {
  path: string;
  operation: string;
  old_value: unknown;
  new_value: unknown;
};

type DiffResult = {
  from_rev: number;
  to_rev: number;
  added: DiffEntry[];
  removed: DiffEntry[];
  changed: DiffEntry[];
};

async function fetchRevisions(
  dppId: string,
  token?: string,
): Promise<Revision[]> {
  const response = await tenantApiFetch(`/dpps/${dppId}/revisions`, {}, token);
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, 'Failed to fetch revisions'),
    );
  }
  return response.json();
}

async function fetchDiff(
  dppId: string,
  fromRev: number,
  toRev: number,
  token?: string,
): Promise<DiffResult> {
  const response = await tenantApiFetch(
    `/dpps/${dppId}/diff?from=${fromRev}&to=${toRev}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, 'Failed to fetch diff'),
    );
  }
  return response.json();
}

type RevisionHistoryProps = {
  dppId: string;
  token?: string;
};

export function RevisionHistory({ dppId, token }: RevisionHistoryProps) {
  const [selectedRevs, setSelectedRevs] = useState<number[]>([]);
  const [comparing, setComparing] = useState(false);

  const { data: revisions, isLoading } = useQuery({
    queryKey: ['revisions', dppId],
    queryFn: () => fetchRevisions(dppId, token),
    enabled: Boolean(token && dppId),
  });

  const fromRev =
    selectedRevs.length === 2 ? Math.min(...selectedRevs) : 0;
  const toRev =
    selectedRevs.length === 2 ? Math.max(...selectedRevs) : 0;

  const { data: diffResult, isLoading: diffLoading } = useQuery({
    queryKey: ['diff', dppId, fromRev, toRev],
    queryFn: () => fetchDiff(dppId, fromRev, toRev, token),
    enabled: comparing && fromRev > 0 && toRev > 0,
  });

  const toggleRevision = (revNo: number) => {
    setComparing(false);
    setSelectedRevs((prev) => {
      if (prev.includes(revNo)) {
        return prev.filter((r) => r !== revNo);
      }
      if (prev.length >= 2) {
        return [prev[1], revNo];
      }
      return [...prev, revNo];
    });
  };

  if (isLoading) return <LoadingSpinner />;
  if (!revisions || revisions.length === 0) return null;

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium">
          <History className="h-4 w-4" />
          {revisions.length} revision{revisions.length !== 1 ? 's' : ''}
        </div>
        {selectedRevs.length === 2 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setComparing(true)}
            disabled={comparing && diffLoading}
          >
            <GitCompareArrows className="h-4 w-4 mr-1" />
            {diffLoading ? 'Loading...' : `Compare #${fromRev} → #${toRev}`}
          </Button>
        )}
      </div>

      <div className="space-y-2">
        {revisions.map((rev) => {
          const isSelected = selectedRevs.includes(rev.revision_no);
          return (
            <button
              key={rev.id}
              onClick={() => toggleRevision(rev.revision_no)}
              className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-colors ${
                isSelected
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:bg-muted/50'
              }`}
            >
              <div className="flex items-center gap-3">
                <Badge variant={isSelected ? 'default' : 'outline'}>
                  #{rev.revision_no}
                </Badge>
                <StatusBadge status={rev.state} />
                <span className="text-sm text-muted-foreground truncate max-w-[200px]">
                  {rev.created_by_subject}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                {formatDate(rev.created_at)}
              </span>
            </button>
          );
        })}
      </div>

      {comparing && diffResult && <DiffViewer diff={diffResult} />}
    </div>
  );
}
