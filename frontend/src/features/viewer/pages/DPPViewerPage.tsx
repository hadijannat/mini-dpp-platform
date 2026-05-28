import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { ChevronDown, Activity, ListTree, ShieldCheck } from 'lucide-react';
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
import { useDisclosurePreference } from '@/features/progressive-disclosure/useDisclosurePreference';
import { Switch } from '@/components/ui/switch';

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

  const submodels = useMemo(
    () => (dpp?.aas_environment?.submodels || []) as Array<Record<string, unknown>>,
    [dpp?.aas_environment?.submodels],
  );
  const classified = useMemo(() => classifySubmodelElements(submodels), [submodels]);
  const defaultCategory = useMemo(
    () => ESPR_CATEGORIES.find((category) => (classified[category.id]?.length ?? 0) > 0)?.id ?? 'identity',
    [classified],
  );
  const [activeCategory, setActiveCategory] = useState(defaultCategory);
  const [selectedOutlineNodeId, setSelectedOutlineNodeId] = useState<string | null>(null);
  const [pendingScrollOutlineKey, setPendingScrollOutlineKey] = useState<string | null>(null);
  const [showOutline, setShowOutline] = useDisclosurePreference('miniDpp.viewer.showOutline');
  const [showTechnicalDetails, setShowTechnicalDetails] = useDisclosurePreference(
    'miniDpp.viewer.technicalDetails',
  );
  const [showTechnicalMetadata, setShowTechnicalMetadata] = useDisclosurePreference(
    'miniDpp.viewer.technicalMetadata',
  );
  const suppressScrollSyncUntilRef = useRef(0);
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
  const passportFacts = useMemo(() => {
    const facts: Array<{ label: string; value: unknown }> = [];
    const preferredLabels = ['ManufacturerName', 'Manufacturer', 'ProductName', 'SerialNumber', 'TotalCO2', 'Mass'];
    const seen = new Set<string>();
    const allFields = Object.values(classified)
      .flat()
      .filter((field) => field.value !== null && field.value !== undefined && field.value !== '');

    for (const label of preferredLabels) {
      const match = allFields.find((field) => field.label === label);
      if (match && !seen.has(match.label)) {
        facts.push({ label: match.label, value: match.value });
        seen.add(match.label);
      }
      if (facts.length >= 6) return facts;
    }

    for (const field of allFields) {
      if (seen.has(field.label)) continue;
      facts.push({ label: field.label, value: field.value });
      seen.add(field.label);
      if (facts.length >= 6) break;
    }

    return facts;
  }, [classified]);

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

  const handleOutlineNodeSelect = useCallback((node: DppOutlineNode) => {
    suppressScrollSyncUntilRef.current = Date.now() + 900;
    setSelectedOutlineNodeId((previous) => (previous === node.id ? previous : node.id));
    const categoryId =
      typeof node.meta?.categoryId === 'string' ? node.meta.categoryId : null;
    if (categoryId) {
      setActiveCategory(categoryId);
    }
    if (node.target?.type !== 'dom' || node.kind !== 'field') return;
    setPendingScrollOutlineKey(node.target.path);
  }, []);

  const handleActiveOutlinePathChange = useCallback(
    (path: string) => {
      if (Date.now() < suppressScrollSyncUntilRef.current) return;
      const outlineNodeId = outlinePathToNodeId.get(path);
      if (outlineNodeId) {
        setSelectedOutlineNodeId((previous) =>
          previous === outlineNodeId ? previous : outlineNodeId,
        );
      }
    },
    [outlinePathToNodeId],
  );

  useOutlineScrollSync({
    enabled: submodels.length > 0,
    attribute: 'data-outline-key',
    onActivePathChange: handleActiveOutlinePathChange,
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
      {submodels.length > 0 && showOutline && (
        <DppOutlinePane
          context="viewer"
          mobile
          className="xl:hidden"
          nodes={outlineNodes}
          selectedId={selectedOutlineNodeId}
          onSelectNode={handleOutlineNodeSelect}
        />
      )}

      <div className={showOutline ? 'xl:grid xl:grid-cols-[minmax(250px,320px)_1fr] xl:gap-6' : ''}>
        {submodels.length > 0 && showOutline ? (
          <DppOutlinePane
            context="viewer"
            className="hidden xl:block"
            nodes={outlineNodes}
            selectedId={selectedOutlineNodeId}
            onSelectNode={handleOutlineNodeSelect}
          />
        ) : null}

        <div className="space-y-6">
      <DPPHeader
        productName={productName}
        dppId={dpp.id}
        status={dpp.status}
        assetIds={dpp.asset_ids}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="h-5 w-5" />
            Passport Summary
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Key product facts and trust signals before the technical passport structure.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Data sections</p>
              <p className="mt-1 text-xl font-semibold">{submodels.length}</p>
            </div>
            <div className="rounded-md border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Supply-chain events</p>
              <p className="mt-1 text-xl font-semibold">{epcisEvents.length}</p>
            </div>
            <div className="rounded-md border bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Integrity status</p>
              <p className="mt-1 text-sm font-medium">
                {dpp.digest_sha256 ? 'Digest available' : 'No digest published'}
              </p>
            </div>
          </div>

          {passportFacts.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold">Important facts</h2>
              <dl className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {passportFacts.map((fact) => (
                  <div key={fact.label} className="rounded-md border p-3">
                    <dt className="text-xs text-muted-foreground">{fact.label}</dt>
                    <dd className="mt-1 text-sm font-medium break-words">{String(fact.value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {submodels.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t pt-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowOutline(!showOutline)}
                aria-expanded={showOutline}
              >
                <ListTree className="mr-2 h-4 w-4" />
                {showOutline ? 'Hide navigation outline' : 'Show navigation outline'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setActiveCategory(defaultCategory)}
              >
                View passport details
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ESPR Category Tabs */}
      {submodels.length > 0 && (
        <Card>
          <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
            <CardTitle>Passport Details</CardTitle>
            <p className="text-sm text-muted-foreground">
              Product data grouped into plain-language sustainability categories.
            </p>
            </div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <Switch
                checked={showTechnicalMetadata}
                onCheckedChange={setShowTechnicalMetadata}
                aria-label="Show technical metadata"
              />
              Show technical metadata
            </label>
          </CardHeader>
          <CardContent>
            <ESPRTabs
              classified={classified}
              value={activeCategory}
              onValueChange={setActiveCategory}
              showTechnicalMetadata={showTechnicalMetadata}
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
        <Collapsible open={showTechnicalDetails} onOpenChange={setShowTechnicalDetails}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between text-muted-foreground">
              Technical AAS Data
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="p-4">
                <p className="mb-3 text-sm text-muted-foreground">
                  For auditors, developers, and standards verification.
                </p>
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
