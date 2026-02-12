import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch, tenantApiFetch, getApiErrorMessage } from '@/lib/api';
import { fetchPublicEPCISEvents } from '@/features/epcis/lib/epcisApi';
import { EPCISTimeline } from '@/features/epcis/components/EPCISTimeline';
import { getTenantSlug } from '@/lib/tenant';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { ChevronDown, Activity } from 'lucide-react';
import { DPPHeader } from '../components/DPPHeader';
import { ESPRTabs } from '../components/ESPRTabs';
import { RawSubmodelTree } from '../components/RawSubmodelTree';
import { IntegrityCard } from '../components/IntegrityCard';
import { classifySubmodelElements, ESPR_CATEGORIES } from '../utils/esprCategories';
import { DppOutlinePane } from '@/features/dpp-outline/components/DppOutlinePane';
import { buildViewerOutline } from '@/features/dpp-outline/builders/buildViewerOutline';
import { useOutlineScrollSync } from '@/features/dpp-outline/hooks/useOutlineScrollSync';
import type { DppOutlineNode } from '@/features/dpp-outline/types';
import type { PublicDPPResponse } from '@/api/types';
import { emitSubmodelUxMetric } from '@/features/submodels/telemetry/uxTelemetry';
import { resolveSubmodelUxRollout } from '@/features/submodels/featureFlags';

async function fetchDPP(
  dppId: string,
  tenantSlug: string,
  token?: string,
  isSlug = false,
): Promise<PublicDPPResponse> {
  // Authenticated users get drafts via tenant API; public visitors use the public endpoint
  if (token) {
    const endpoint = isSlug ? `/dpps/by-slug/${dppId}` : `/dpps/${dppId}`;
    const response = await tenantApiFetch(endpoint, {}, token, tenantSlug);
    if (!response.ok) {
      throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
    }
    return response.json() as Promise<PublicDPPResponse>;
  }
  const basePath = `/api/v1/public/${encodeURIComponent(tenantSlug)}/dpps`;
  const endpoint = isSlug
    ? `${basePath}/slug/${encodeURIComponent(dppId)}`
    : `${basePath}/${encodeURIComponent(dppId)}`;
  const response = await apiFetch(endpoint);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json() as Promise<PublicDPPResponse>;
}

export default function DPPViewerPage() {
  const { dppId, slug, tenantSlug } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const token = auth.isAuthenticated ? auth.user?.access_token : undefined;
  const id = dppId || slug;
  const isSlug = !dppId && !!slug;
  const resolvedTenant = tenantSlug || getTenantSlug();
  const rollout = resolveSubmodelUxRollout(resolvedTenant);

  const { data: dpp, isLoading, error } = useQuery<PublicDPPResponse>({
    queryKey: ['dpp', resolvedTenant, id, isSlug, !!token],
    queryFn: () => fetchDPP(id!, resolvedTenant, token, isSlug),
    enabled: !!id && !!resolvedTenant,
  });

  // EPCIS events — fetched via public endpoint (no auth needed)
  const dppUuid = (dpp?.id as string) ?? '';
  const { data: epcisData } = useQuery({
    queryKey: ['epcis-events', 'viewer', resolvedTenant, dppUuid],
    queryFn: () => fetchPublicEPCISEvents(resolvedTenant, dppUuid),
    enabled: !!dppUuid && !!resolvedTenant,
  });

  const submodels = (dpp?.aas_environment?.submodels || []) as Array<Record<string, unknown>>;
  const classified = classifySubmodelElements(submodels);
  const defaultCategory = useMemo(
    () => ESPR_CATEGORIES.find((category) => (classified[category.id]?.length ?? 0) > 0)?.id ?? 'identity',
    [classified],
  );
  const [activeCategory, setActiveCategory] = useState(defaultCategory);
  const [selectedOutlineNodeId, setSelectedOutlineNodeId] = useState<string | null>(null);
  const [pendingScrollOutlineKey, setPendingScrollOutlineKey] = useState<string | null>(null);
  const outlineNodes = useMemo(
    () =>
      buildViewerOutline({
        categories: ESPR_CATEGORIES,
        classified,
      }),
    [classified],
  );
  const outlinePathToNodeId = useMemo(() => {
    const map = new Map<string, string>();
    const stack = [...outlineNodes];
    while (stack.length > 0) {
      const current = stack.pop()!;
      if (current.target?.type === 'dom') {
        map.set(current.target.path, current.id);
      }
      for (const child of current.children) {
        stack.push(child);
      }
    }
    return map;
  }, [outlineNodes]);
  const productName =
    (dpp?.asset_ids?.manufacturerPartId as string) || 'Digital Product Passport';
  const epcisEvents = epcisData?.eventList ?? [];

  useEffect(() => {
    setActiveCategory(defaultCategory);
  }, [defaultCategory]);

  useEffect(() => {
    if (!pendingScrollOutlineKey) return;

    let timeoutId: number | undefined;
    let attempts = 0;

    const scrollToPending = () => {
      attempts += 1;
      const target = Array.from(document.querySelectorAll<HTMLElement>('[data-outline-key]')).find(
        (element) => element.dataset.outlineKey === pendingScrollOutlineKey,
      );
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setPendingScrollOutlineKey(null);
        return;
      }
      if (attempts < 8) {
        timeoutId = window.setTimeout(scrollToPending, 60);
      } else {
        setPendingScrollOutlineKey(null);
      }
    };

    scrollToPending();

    return () => {
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [activeCategory, pendingScrollOutlineKey]);

  const handleOutlineNodeSelect = (node: DppOutlineNode) => {
    setSelectedOutlineNodeId(node.id);
    const categoryId =
      typeof node.meta?.categoryId === 'string' ? node.meta.categoryId : null;
    if (categoryId) {
      setActiveCategory(categoryId);
    }
    if (node.target?.type !== 'dom' || node.kind !== 'field') return;
    setPendingScrollOutlineKey(node.target.path);
  };

  useOutlineScrollSync({
    enabled: submodels.length > 0,
    attribute: 'data-outline-key',
    onActivePathChange: (path) => {
      const outlineNodeId = outlinePathToNodeId.get(path);
      if (outlineNodeId) {
        setSelectedOutlineNodeId(outlineNodeId);
      }
    },
  });

  useEffect(() => {
    if (!dpp?.id || submodels.length === 0) return;
    const uncategorized = classified.uncategorized ?? [];
    const withSemanticId = uncategorized.filter((node) => Boolean(node.semanticId)).length;
    emitSubmodelUxMetric('unresolved_semantic_classification', {
      dpp_id: dpp.id,
      uncategorized_count: uncategorized.length,
      uncategorized_with_semantic_id: withSemanticId,
    });
  }, [classified, dpp?.id, submodels.length]);

  if (isLoading) return <LoadingSpinner />;

  if (error) {
    const message = (error as Error)?.message || '';
    const isAuthError = message.includes('Session expired') || message.includes('401');
    return (
      <ErrorBanner
        message={
          isAuthError
            ? 'This passport requires authentication to view. Please sign in.'
            : message || 'Error loading Digital Product Passport'
        }
        showSignIn={isAuthError}
        onSignIn={isAuthError ? () => navigate('/login') : undefined}
      />
    );
  }

  if (!dpp) {
    return <ErrorBanner message="Digital Product Passport not found" />;
  }

  return (
    <div className="space-y-4">
      {submodels.length > 0 && (
        <DppOutlinePane
          context="viewer"
          mobile
          className="xl:hidden"
          nodes={outlineNodes}
          selectedId={selectedOutlineNodeId}
          onSelectNode={handleOutlineNodeSelect}
        />
      )}

      <div className="xl:grid xl:grid-cols-[minmax(250px,320px)_1fr] xl:gap-6">
        {submodels.length > 0 ? (
          <DppOutlinePane
            context="viewer"
            className="hidden xl:block"
            nodes={outlineNodes}
            selectedId={selectedOutlineNodeId}
            onSelectNode={handleOutlineNodeSelect}
          />
        ) : (
          <div className="hidden xl:block" />
        )}

        <div className="space-y-6">
      <DPPHeader
        productName={productName}
        dppId={dpp.id}
        status={dpp.status}
        assetIds={dpp.asset_ids}
      />

      {/* ESPR Category Tabs */}
      {submodels.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Product Information</CardTitle>
            <p className="text-sm text-muted-foreground">
              Organized per EU ESPR (European Sustainability Product Regulation) categories
            </p>
          </CardHeader>
          <CardContent>
            <ESPRTabs
              classified={classified}
              value={activeCategory}
              onValueChange={setActiveCategory}
            />
          </CardContent>
        </Card>
      )}

      {/* Supply Chain Traceability */}
      {epcisEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Supply Chain Journey
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              EPCIS 2.0 traceability events for this product
            </p>
          </CardHeader>
          <CardContent>
            <EPCISTimeline events={epcisEvents} />
          </CardContent>
        </Card>
      )}

      {/* Raw Data (for advanced users/regulators) */}
      {submodels.length > 0 && rollout.surfaces.viewer && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between text-muted-foreground">
              Raw Submodel Data (Advanced)
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="p-4">
                <RawSubmodelTree submodels={submodels} />
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Integrity */}
      {dpp.digest_sha256 && <IntegrityCard digest={dpp.digest_sha256} />}
        </div>
      </div>
    </div>
  );
}
