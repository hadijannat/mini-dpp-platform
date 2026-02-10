import { useEffect, useState, useCallback } from 'react';
import { useAuth } from 'react-oidc-context';
import { Loader2 } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { ConfirmDialog } from '@/components/confirm-dialog';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';

interface RoleRequest {
  id: string;
  user_subject: string;
  requested_role: string;
  status: string;
  reason: string | null;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
}

const statusBadgeVariant: Record<string, 'default' | 'secondary' | 'destructive'> = {
  pending: 'default',
  approved: 'secondary',
  denied: 'destructive',
};

export default function RoleRequestsPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;

  const [requests, setRequests] = useState<RoleRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewAction, setReviewAction] = useState<'approve' | 'deny' | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRequests = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = statusFilter !== 'all' ? `?status_filter=${statusFilter}` : '';
      const resp = await tenantApiFetch(`/role-requests${params}`, {}, token);
      if (!resp.ok) throw new Error(await getApiErrorMessage(resp, 'Failed to load requests'));
      const data = (await resp.json()) as RoleRequest[];
      setRequests(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  async function handleReview(approved: boolean) {
    if (!token || !reviewingId) return;
    setReviewLoading(true);
    try {
      const resp = await tenantApiFetch(
        `/role-requests/${reviewingId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved }),
        },
        token
      );
      if (!resp.ok) throw new Error(await getApiErrorMessage(resp, 'Review failed'));
      setReviewingId(null);
      setReviewAction(null);
      await loadRequests();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setReviewLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Role Requests"
        description="Review and manage user role upgrade requests."
      />

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="denied">Denied</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : requests.length === 0 ? (
        <p className="text-center text-muted-foreground py-12">No role requests found.</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Requested Role</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((req) => (
                <TableRow key={req.id}>
                  <TableCell className="font-mono text-xs max-w-[200px] truncate">
                    {req.user_subject}
                  </TableCell>
                  <TableCell className="capitalize">{req.requested_role}</TableCell>
                  <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                    {req.reason || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusBadgeVariant[req.status] ?? 'default'} className="capitalize">
                      {req.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(req.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {req.status === 'pending' && (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="default"
                          onClick={() => {
                            setReviewingId(req.id);
                            setReviewAction('approve');
                          }}
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => {
                            setReviewingId(req.id);
                            setReviewAction('deny');
                          }}
                        >
                          Deny
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Approve dialog */}
      <ConfirmDialog
        open={reviewAction === 'approve'}
        onOpenChange={(open) => {
          if (!open) {
            setReviewAction(null);
            setReviewingId(null);
          }
        }}
        title="Approve Role Request"
        description="This will upgrade the user's role to publisher. They will gain the ability to create and manage DPPs."
        confirmLabel="Approve"
        loading={reviewLoading}
        onConfirm={() => handleReview(true)}
      />

      {/* Deny dialog */}
      <ConfirmDialog
        open={reviewAction === 'deny'}
        onOpenChange={(open) => {
          if (!open) {
            setReviewAction(null);
            setReviewingId(null);
          }
        }}
        title="Deny Role Request"
        description="This will deny the role upgrade request. The user will remain a viewer."
        confirmLabel="Deny"
        variant="destructive"
        loading={reviewLoading}
        onConfirm={() => handleReview(false)}
      />
    </div>
  );
}
