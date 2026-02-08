import { useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Globe } from 'lucide-react';
import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ErrorBanner } from '@/components/error-banner';
import { EmptyState } from '@/components/empty-state';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ConfirmDialog } from '@/components/confirm-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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

const LINK_TYPES = [
  'gs1:hasDigitalProductPassport',
  'gs1:pip',
  'gs1:certificationInfo',
  'gs1:epil',
  'gs1:defaultLink',
  'gs1:productSustainabilityInfo',
  'gs1:quickStartGuide',
  'gs1:support',
  'gs1:registration',
  'gs1:recallStatus',
  'iec61406:identificationLink',
] as const;

interface ResolverLink {
  id: string;
  tenant_id: string;
  identifier: string;
  link_type: string;
  href: string;
  media_type: string;
  title: string;
  hreflang: string;
  priority: number;
  dpp_id: string | null;
  active: boolean;
  created_by_subject: string;
  created_at: string;
  updated_at: string;
}

function linkTypeBadgeVariant(linkType: string): 'default' | 'secondary' | 'outline' {
  if (linkType === 'gs1:hasDigitalProductPassport') return 'default';
  if (linkType === 'gs1:defaultLink') return 'secondary';
  if (linkType.startsWith('iec61406:')) return 'default';
  return 'outline';
}

function linkTypeLabel(linkType: string): string {
  if (linkType.startsWith('iec61406:')) return linkType.replace('iec61406:', '');
  return linkType.replace('gs1:', '');
}

export default function ResolverPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const slug = getTenantSlug();

  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [newIdentifier, setNewIdentifier] = useState('');
  const [newLinkType, setNewLinkType] = useState<string>('gs1:hasDigitalProductPassport');
  const [newHref, setNewHref] = useState('');
  const [newMediaType, setNewMediaType] = useState('application/json');
  const [newTitle, setNewTitle] = useState('');
  const [newHreflang, setNewHreflang] = useState('en');
  const [newPriority, setNewPriority] = useState(0);

  const { data: links, isLoading } = useQuery<ResolverLink[]>({
    queryKey: ['resolver-links', slug],
    queryFn: async () => {
      const res = await tenantApiFetch('/resolver/', {}, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to load resolver links'));
      return res.json();
    },
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await tenantApiFetch('/resolver/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: newIdentifier,
          link_type: newLinkType,
          href: newHref,
          media_type: newMediaType,
          title: newTitle,
          hreflang: newHreflang,
          priority: newPriority,
        }),
      }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to create resolver link'));
      return res.json();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['resolver-links'] });
      resetCreateForm();
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) => {
      const res = await tenantApiFetch(`/resolver/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
      }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to update link'));
      return res.json();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['resolver-links'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await tenantApiFetch(`/resolver/${id}`, { method: 'DELETE' }, token!);
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to delete link'));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['resolver-links'] });
      setDeleteId(null);
    },
  });

  function resetCreateForm() {
    setCreateOpen(false);
    setNewIdentifier('');
    setNewLinkType('gs1:hasDigitalProductPassport');
    setNewHref('');
    setNewMediaType('application/json');
    setNewTitle('');
    setNewHreflang('en');
    setNewPriority(0);
  }

  if (isLoading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resolver"
        description="Manage GS1 Digital Link resolver entries for your products"
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Link
          </Button>
        }
      />

      {error && <ErrorBanner message={error} showSignIn={false} onSignIn={() => {}} />}

      {!links?.length ? (
        <EmptyState
          icon={Globe}
          title="No resolver links"
          description="Create resolver links to enable GS1 Digital Link resolution for your products."
        />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Identifier</TableHead>
                <TableHead>Link Type</TableHead>
                <TableHead>Target URL</TableHead>
                <TableHead className="text-center">Priority</TableHead>
                <TableHead className="text-center">Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {links.map(link => (
                <TableRow key={link.id}>
                  <TableCell className="font-mono text-xs max-w-[200px] truncate">
                    {link.identifier}
                  </TableCell>
                  <TableCell>
                    <Badge variant={linkTypeBadgeVariant(link.link_type)}>
                      {linkTypeLabel(link.link_type)}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs max-w-[250px] truncate">
                    {link.href}
                  </TableCell>
                  <TableCell className="text-center">{link.priority}</TableCell>
                  <TableCell className="text-center">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        void toggleMutation.mutateAsync({ id: link.id, active: !link.active });
                      }}
                    >
                      <Badge variant={link.active ? 'default' : 'outline'}>
                        {link.active ? 'Active' : 'Inactive'}
                      </Badge>
                    </Button>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteId(link.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={(open) => { if (!open) resetCreateForm(); else setCreateOpen(true); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add Resolver Link</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="resolver-identifier">Identifier</Label>
              <Input
                id="resolver-identifier"
                placeholder="01/09520123456788/21/SERIAL001"
                value={newIdentifier}
                onChange={e => setNewIdentifier(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">GS1 identifier stem (AI path)</p>
            </div>
            <div>
              <Label htmlFor="resolver-link-type">Link Type</Label>
              <Select value={newLinkType} onValueChange={setNewLinkType}>
                <SelectTrigger id="resolver-link-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LINK_TYPES.map(lt => (
                    <SelectItem key={lt} value={lt}>{linkTypeLabel(lt)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="resolver-href">Target URL</Label>
              <Input
                id="resolver-href"
                placeholder="https://example.com/dpp/..."
                value={newHref}
                onChange={e => setNewHref(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="resolver-media-type">Media Type</Label>
                <Input
                  id="resolver-media-type"
                  value={newMediaType}
                  onChange={e => setNewMediaType(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="resolver-hreflang">Language</Label>
                <Input
                  id="resolver-hreflang"
                  value={newHreflang}
                  onChange={e => setNewHreflang(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="resolver-title">Title</Label>
                <Input
                  id="resolver-title"
                  placeholder="Product Passport"
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="resolver-priority">Priority</Label>
                <Input
                  id="resolver-priority"
                  type="number"
                  min={0}
                  max={1000}
                  value={newPriority}
                  onChange={e => setNewPriority(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={resetCreateForm}>Cancel</Button>
            <Button
              onClick={() => { void createMutation.mutateAsync(); }}
              disabled={!newIdentifier || !newHref || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Link'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={open => { if (!open) setDeleteId(null); }}
        title="Delete Resolver Link"
        description="This will permanently remove the resolver link. Products using this link will no longer resolve."
        confirmLabel="Delete"
        variant="destructive"
        loading={deleteMutation.isPending}
        onConfirm={() => { if (deleteId) void deleteMutation.mutateAsync(deleteId); }}
      />
    </div>
  );
}
