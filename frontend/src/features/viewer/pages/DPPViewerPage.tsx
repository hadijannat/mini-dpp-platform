import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { getTenantSlug } from '@/lib/tenant';

async function fetchDPP(dppId: string, tenantSlug: string, token?: string, isSlug = false) {
  const endpoint = isSlug ? `/dpps/by-slug/${dppId}` : `/dpps/${dppId}`;
  const response = await tenantApiFetch(endpoint, {}, token, tenantSlug);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch DPP'));
  }
  return response.json();
}

function formatElementValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return '[object]';
  }
}

export default function DPPViewerPage() {
  const { dppId, slug, tenantSlug } = useParams();
  const id = dppId || slug;
  const isSlug = !dppId && !!slug;
  const resolvedTenant = tenantSlug || getTenantSlug();
  const auth = useAuth();
  const token = auth.user?.access_token;

  const { data: dpp, isLoading, error } = useQuery({
    queryKey: ['dpp', resolvedTenant, id, isSlug],
    queryFn: () => fetchDPP(id!, resolvedTenant, token, isSlug),
    enabled: !!id && !!resolvedTenant,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">
          {(error as Error)?.message || 'Error loading Digital Product Passport'}
        </p>
      </div>
    );
  }

  if (!dpp) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800">Digital Product Passport not found</p>
      </div>
    );
  }

  const submodels = dpp.aas_environment?.submodels || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Digital Product Passport
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          ID: {dpp.id}
        </p>
        <div className="mt-4 flex items-center space-x-4">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            dpp.status === 'published'
              ? 'bg-green-100 text-green-800'
              : 'bg-yellow-100 text-yellow-800'
          }`}>
            {dpp.status}
          </span>
        </div>
      </div>

      {/* Asset Information */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Asset Information
        </h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Object.entries(dpp.asset_ids || {}).map(([key, value]) => (
            <div key={key}>
              <dt className="text-sm font-medium text-gray-500">{key}</dt>
              <dd className="mt-1 text-sm text-gray-900">{String(value)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* AAS Environment */}
      {dpp.aas_environment && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Submodels
          </h2>
          <div className="space-y-4">
            {submodels.length === 0 && (
              <p className="text-sm text-gray-500">
                No submodels yet. Add templates in the console to initialize this DPP.
              </p>
            )}
            {submodels.map((submodel: any, index: number) => (
              <div key={index} className="border rounded-lg p-4">
                <h3 className="font-medium text-gray-900">{submodel.idShort}</h3>
                <p className="text-sm text-gray-500">{submodel.id}</p>
                {submodel.submodelElements && (
                  <div className="mt-4 space-y-2">
                    {submodel.submodelElements.map((element: any, idx: number) => (
                      <div key={idx} className="flex justify-between text-sm">
                        <span className="text-gray-600">{element.idShort}</span>
                        <span className="text-gray-900">
                          {formatElementValue(element.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Integrity */}
      {dpp.digest_sha256 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Integrity
          </h2>
          <div>
            <dt className="text-sm font-medium text-gray-500">SHA-256 Digest</dt>
            <dd className="mt-1 text-xs font-mono text-gray-900 break-all">
              {dpp.digest_sha256}
            </dd>
          </div>
        </div>
      )}
    </div>
  );
}
