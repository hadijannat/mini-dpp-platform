import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
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
import { classifySubmodelElements } from '../utils/esprCategories';
import type { PublicDPPResponse } from '@/api/types';

async function fetchDPP(
  dppId: string,
  tenantSlug: string,
  isSlug = false,
): Promise<PublicDPPResponse> {
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
  const id = dppId || slug;
  const isSlug = !dppId && !!slug;
  const resolvedTenant = tenantSlug || getTenantSlug();

  const { data: dpp, isLoading, error } = useQuery<PublicDPPResponse>({
    queryKey: ['dpp', resolvedTenant, id, isSlug],
    queryFn: () => fetchDPP(id!, resolvedTenant, isSlug),
    enabled: !!id && !!resolvedTenant,
  });

  // EPCIS events — fetched via public endpoint (no auth needed)
  const dppUuid = (dpp?.id as string) ?? '';
  const { data: epcisData } = useQuery({
    queryKey: ['epcis-events', 'viewer', resolvedTenant, dppUuid],
    queryFn: () => fetchPublicEPCISEvents(resolvedTenant, dppUuid),
    enabled: !!dppUuid && !!resolvedTenant,
  });

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

  const submodels = (dpp.aas_environment?.submodels || []) as Array<Record<string, unknown>>;
  const classified = classifySubmodelElements(submodels);
  const productName =
    (dpp.asset_ids?.manufacturerPartId as string) || 'Digital Product Passport';
  const epcisEvents = epcisData?.eventList ?? [];

  return (
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
            <ESPRTabs classified={classified} />
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
      {submodels.length > 0 && (
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
  );
}
