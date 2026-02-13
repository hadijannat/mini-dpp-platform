import { Fragment, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useQuery } from '@tanstack/react-query';
import { Search, ChevronDown, ChevronRight, Database } from 'lucide-react';
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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface SubmodelDescriptor {
  id: string;
  idShort?: string;
  semanticId?: {
    keys?: Array<{ value: string }>;
  };
  endpoints?: Array<{
    interface: string;
    protocolInformation: { href: string };
  }>;
  [key: string]: unknown;
}

interface ShellDescriptor {
  id: string;
  tenant_id: string;
  aas_id: string;
  id_short: string;
  global_asset_id: string;
  specific_asset_ids: Array<{ name: string; value: string }>;
  submodel_descriptors: SubmodelDescriptor[];
  dpp_id: string | null;
  created_by_subject: string;
  created_at: string;
  updated_at: string;
}

export default function RegistryPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const slug = getTenantSlug();

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchKey, setSearchKey] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [activeSearch, setActiveSearch] = useState<{ key: string; value: string } | null>(null);
  const [discoveryKey, setDiscoveryKey] = useState('');
  const [discoveryValue, setDiscoveryValue] = useState('');
  const [activeDiscovery, setActiveDiscovery] = useState<{ key: string; value: string } | null>(null);

  const { data: descriptors, isLoading, error: fetchError } = useQuery<ShellDescriptor[]>({
    queryKey: ['registry-descriptors', slug],
    queryFn: async () => {
      const res = await tenantApiFetch('/registry/shell-descriptors', {}, token ?? '');
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to load shell descriptors'));
      return res.json();
    },
    enabled: !!token,
  });

  const { data: searchResults, isFetching: isSearching } = useQuery<ShellDescriptor[]>({
    queryKey: ['registry-search', slug, activeSearch?.key, activeSearch?.value],
    queryFn: async () => {
      const res = await tenantApiFetch('/registry/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id_key: activeSearch!.key,
          asset_id_value: activeSearch!.value,
        }),
      }, token ?? '');
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Search failed'));
      return res.json();
    },
    enabled: !!token && !!activeSearch,
  });

  const { data: discoveryResults, isFetching: isDiscovering } = useQuery<string[]>({
    queryKey: ['registry-discovery', slug, activeDiscovery?.key, activeDiscovery?.value],
    queryFn: async () => {
      const params = new URLSearchParams({
        asset_id_key: activeDiscovery!.key,
        asset_id_value: activeDiscovery!.value,
      });
      const res = await tenantApiFetch(`/registry/discovery?${params.toString()}`, {}, token ?? '');
      if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Discovery lookup failed'));
      return res.json();
    },
    enabled: !!token && !!activeDiscovery,
  });

  function handleSearch() {
    if (searchKey && searchValue) {
      setActiveSearch({ key: searchKey, value: searchValue });
    }
  }

  function handleDiscovery() {
    if (discoveryKey && discoveryValue) {
      setActiveDiscovery({ key: discoveryKey, value: discoveryValue });
    }
  }

  function getSemanticId(sm: SubmodelDescriptor): string {
    const keys = sm.semanticId?.keys;
    if (keys && keys.length > 0) return keys[0].value;
    return '';
  }

  if (isLoading) return <LoadingSpinner size="lg" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Registry"
        description="Browse and search AAS shell descriptors in the built-in registry"
      />

      {fetchError && (
        <ErrorBanner
          message={fetchError instanceof Error ? fetchError.message : 'Failed to load descriptors'}
          showSignIn={false}
          onSignIn={() => {}}
        />
      )}

      {/* Search and Discovery panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Search by Asset ID */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Search by Asset ID</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="search-key" className="text-xs">Key</Label>
                <Input
                  id="search-key"
                  placeholder="globalAssetId"
                  value={searchKey}
                  onChange={e => setSearchKey(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label htmlFor="search-value" className="text-xs">Value</Label>
                <Input
                  id="search-value"
                  placeholder="urn:example:asset:1"
                  value={searchValue}
                  onChange={e => setSearchValue(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <Button
              size="sm"
              onClick={handleSearch}
              disabled={!searchKey || !searchValue || isSearching}
            >
              <Search className="h-3 w-3 mr-1" />
              {isSearching ? 'Searching...' : 'Search'}
            </Button>
            {searchResults && (
              <p className="text-xs text-muted-foreground">
                {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} found
              </p>
            )}
          </CardContent>
        </Card>

        {/* Discovery Lookup */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Discovery Lookup</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="discovery-key" className="text-xs">Asset ID Key</Label>
                <Input
                  id="discovery-key"
                  placeholder="serialNumber"
                  value={discoveryKey}
                  onChange={e => setDiscoveryKey(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label htmlFor="discovery-value" className="text-xs">Asset ID Value</Label>
                <Input
                  id="discovery-value"
                  placeholder="SN-12345"
                  value={discoveryValue}
                  onChange={e => setDiscoveryValue(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <Button
              size="sm"
              onClick={handleDiscovery}
              disabled={!discoveryKey || !discoveryValue || isDiscovering}
            >
              <Search className="h-3 w-3 mr-1" />
              {isDiscovering ? 'Looking up...' : 'Lookup'}
            </Button>
            {discoveryResults && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">
                  {discoveryResults.length} AAS ID{discoveryResults.length !== 1 ? 's' : ''} found
                </p>
                {discoveryResults.map(aasId => (
                  <p key={aasId} className="text-xs font-mono bg-muted px-2 py-1 rounded">
                    {aasId}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Shell Descriptors Table */}
      {!descriptors?.length ? (
        <EmptyState
          icon={Database}
          title="No shell descriptors"
          description="Shell descriptors will appear here when DPPs are registered in the AAS registry."
        />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead>AAS ID</TableHead>
                <TableHead>ID Short</TableHead>
                <TableHead>Global Asset ID</TableHead>
                <TableHead className="text-center">Submodels</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(searchResults && activeSearch ? searchResults : descriptors).map(desc => (
                <Fragment key={desc.id}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => setExpandedId(expandedId === desc.id ? null : desc.id)}
                  >
                    <TableCell>
                      {expandedId === desc.id
                        ? <ChevronDown className="h-4 w-4" />
                        : <ChevronRight className="h-4 w-4" />}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">
                      {desc.aas_id}
                    </TableCell>
                    <TableCell className="text-sm">{desc.id_short || '-'}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">
                      {desc.global_asset_id || '-'}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="secondary">{desc.submodel_descriptors.length}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(desc.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                  {expandedId === desc.id && (
                    <TableRow key={`${desc.id}-detail`}>
                      <TableCell colSpan={6} className="bg-muted/50 p-4">
                        <div className="space-y-3">
                          {desc.specific_asset_ids.length > 0 && (
                            <div>
                              <p className="text-xs font-medium mb-1">Specific Asset IDs</p>
                              <div className="flex flex-wrap gap-1">
                                {desc.specific_asset_ids.map((assetId, i) => (
                                  <Badge key={i} variant="outline" className="text-xs">
                                    {assetId.name}: {assetId.value}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          <div>
                            <p className="text-xs font-medium mb-1">
                              Submodel Descriptors ({desc.submodel_descriptors.length})
                            </p>
                            {desc.submodel_descriptors.length === 0 ? (
                              <p className="text-xs text-muted-foreground">No submodels registered</p>
                            ) : (
                              <div className="rounded border bg-background">
                                <Table>
                                  <TableHeader>
                                    <TableRow>
                                      <TableHead className="text-xs">ID Short</TableHead>
                                      <TableHead className="text-xs">Semantic ID</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {desc.submodel_descriptors.map((sm, i) => (
                                      <TableRow key={i}>
                                        <TableCell className="text-xs">{sm.idShort || sm.id}</TableCell>
                                        <TableCell className="text-xs font-mono max-w-[300px] truncate">
                                          {getSemanticId(sm) || '-'}
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
