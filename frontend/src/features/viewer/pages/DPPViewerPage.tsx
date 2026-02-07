import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { ChevronDown } from 'lucide-react';
import { DPPHeader } from '../components/DPPHeader';
import { ESPRTabs } from '../components/ESPRTabs';
import { RawSubmodelTree } from '../components/RawSubmodelTree';
import { IntegrityCard } from '../components/IntegrityCard';
import { classifySubmodelElements } from '../utils/esprCategories';

async function fetchDPP(dppId: string, tenantSlug: string, token?: string, isSlug = false) {
  const endpoint = isSlug ? `/dpps/by-slug/${dppId}` : `/dpps/${dppId}`;
  const response = await tenantApiFetch(endpoint, {}, token, tenantSlug);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json();
}

export default function DPPViewerPage() {
  const { dppId, slug, tenantSlug } = useParams();
  const navigate = useNavigate();
  const id = dppId || slug;
  const isSlug = !dppId && !!slug;
  const resolvedTenant = tenantSlug || getTenantSlug();
  const auth = useAuth();
  // Token is optional -- unauthenticated visitors can view published DPPs
  // once the backend public endpoint is available.
  const token = auth.isAuthenticated ? auth.user?.access_token : undefined;

  const { data: dpp, isLoading, error } = useQuery({
    queryKey: ['dpp', resolvedTenant, id, isSlug],
    queryFn: () => fetchDPP(id!, resolvedTenant, token, isSlug),
    enabled: !!id && !!resolvedTenant,
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
