import { useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, TestTube, ChevronDown, ChevronRight } from 'lucide-react';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { EmptyState } from '@/components/empty-state';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
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

const EVENT_TYPES = [
  'DPP_CREATED',
  'DPP_PUBLISHED',
  'DPP_ARCHIVED',
  'DPP_EXPORTED',
  'EPCIS_CAPTURED',
] as const;

interface Webhook {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_by_subject: string;
  created_at: string;
  updated_at: string;
}

interface Delivery {
  id: string;
  subscription_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  http_status: number | null;
  response_body: string | null;
  attempt: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

export default function WebhooksPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const slug = getTenantSlug();

  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [newUrl, setNewUrl] = useState('');
  const [newEvents, setNewEvents] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const { data: webhooks, isLoading } = useQuery<Webhook[]>({
    queryKey: ['webhooks', slug],
    queryFn: async () => {
      const res = await tenantApiFetch('/webhooks', {}, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to load webhooks'));
      return res.json();
    },
    enabled: !!token,
  });

  const { data: deliveries } = useQuery<Delivery[]>({
    queryKey: ['webhook-deliveries', expandedId],
    queryFn: async () => {
      const res = await tenantApiFetch(`/webhooks/${expandedId}/deliveries`, {}, token!);
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!token && !!expandedId,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await tenantApiFetch('/webhooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newUrl, events: Array.from(newEvents) }),
      }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to create webhook'));
      return res.json();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setCreateOpen(false);
      setNewUrl('');
      setNewEvents(new Set());
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await tenantApiFetch(`/webhooks/${id}`, { method: 'DELETE' }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to delete webhook'));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setDeleteId(null);
    },
  });

  const testMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await tenantApiFetch(`/webhooks/${id}/test`, { method: 'POST' }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Test failed'));
    },
    onSuccess: () => {
      if (expandedId) {
        void queryClient.invalidateQueries({ queryKey: ['webhook-deliveries', expandedId] });
      }
    },
  });

  const toggleEvent = (event: string) => {
    setNewEvents(prev => {
      const next = new Set(prev);
      if (next.has(event)) next.delete(event);
      else next.add(event);
      return next;
    });
  };

  if (isLoading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Webhooks"
        description="Receive HTTP notifications for DPP lifecycle events"
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Webhook
          </Button>
        }
      />

      {error && <ErrorBanner message={error} showSignIn={false} onSignIn={() => {}} />}

      {!webhooks?.length ? (
        <EmptyState
          icon={TestTube}
          title="No webhooks configured"
          description="Add a webhook to receive notifications when DPPs are created, published, or exported."
        />
      ) : (
        <div className="space-y-4">
          {webhooks.map(wh => (
            <Card key={wh.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setExpandedId(expandedId === wh.id ? null : wh.id)}
                      className="p-1 hover:bg-muted rounded"
                    >
                      {expandedId === wh.id
                        ? <ChevronDown className="h-4 w-4" />
                        : <ChevronRight className="h-4 w-4" />}
                    </button>
                    <div>
                      <CardTitle className="text-sm font-mono">{wh.url}</CardTitle>
                      <div className="flex gap-1 mt-1">
                        {wh.events.map(e => (
                          <Badge key={e} variant="secondary" className="text-xs">{e}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={wh.active ? 'default' : 'outline'}>
                      {wh.active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => { void testMutation.mutateAsync(wh.id); }}
                      title="Send test webhook"
                    >
                      <TestTube className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteId(wh.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardHeader>

              {expandedId === wh.id && (
                <CardContent className="pt-0">
                  <h4 className="text-sm font-medium mb-2">Recent Deliveries</h4>
                  {!deliveries?.length ? (
                    <p className="text-xs text-muted-foreground">No deliveries yet</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Event</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Attempt</TableHead>
                          <TableHead>Time</TableHead>
                          <TableHead>Error</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {deliveries.map(d => (
                          <TableRow key={d.id}>
                            <TableCell className="text-xs">{d.event_type}</TableCell>
                            <TableCell>
                              <Badge variant={d.success ? 'default' : 'destructive'} className="text-xs">
                                {d.http_status ?? 'N/A'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs">{d.attempt}</TableCell>
                            <TableCell className="text-xs">
                              {new Date(d.created_at).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-xs text-destructive">
                              {d.error_message || '-'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Webhook</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="webhook-url">URL</Label>
              <Input
                id="webhook-url"
                placeholder="https://example.com/webhook"
                value={newUrl}
                onChange={e => setNewUrl(e.target.value)}
              />
            </div>
            <div>
              <Label>Events</Label>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {EVENT_TYPES.map(event => (
                  <label key={event} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={newEvents.has(event)}
                      onCheckedChange={() => toggleEvent(event)}
                    />
                    {event}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              onClick={() => { void createMutation.mutateAsync(); }}
              disabled={!newUrl || newEvents.size === 0 || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Webhook'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={open => { if (!open) setDeleteId(null); }}
        title="Delete Webhook"
        description="This will permanently remove the webhook subscription and all delivery logs."
        confirmLabel="Delete"
        variant="destructive"
        loading={deleteMutation.isPending}
        onConfirm={() => { if (deleteId) void deleteMutation.mutateAsync(deleteId); }}
      />
    </div>
  );
}
