import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

type GlobalIdSettingsResponse = {
  global_asset_id_base_uri: string;
};

type DataCarrierComplianceProfile = {
  name: string;
  allowed_carrier_types: Array<'qr' | 'datamatrix' | 'nfc'>;
  default_identity_level: 'model' | 'batch' | 'item';
  allowed_identity_levels: Array<'model' | 'batch' | 'item'>;
  allowed_identifier_schemes: Array<'gs1_gtin' | 'iec61406' | 'direct_url'>;
  publish_allowed_statuses: Array<'active' | 'deprecated' | 'withdrawn'>;
  publish_require_active_carrier: boolean;
  publish_require_pre_sale_enabled: boolean;
  enforce_gtin_verified: boolean;
};

type DataCarrierComplianceSettingsResponse = {
  publish_gate_enabled: boolean;
  profile: DataCarrierComplianceProfile;
};

type CENProfileDiagnosticsResponse = {
  enabled: boolean;
  profile_18219: string;
  profile_18220: string;
  profile_18222: string;
  standards_header: string;
};

async function fetchGlobalAssetIdBaseUri(token?: string) {
  const response = await apiFetch('/api/v1/admin/settings/global-asset-id-base-uri', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch settings'));
  }
  return response.json();
}

async function updateGlobalAssetIdBaseUri(value: string, token?: string) {
  const response = await apiFetch(
    '/api/v1/admin/settings/global-asset-id-base-uri',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ global_asset_id_base_uri: value }),
    },
    token
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to update settings'));
  }
  return response.json();
}

async function fetchDataCarrierComplianceSettings(token?: string) {
  const response = await apiFetch('/api/v1/admin/settings/data-carrier-compliance', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch data carrier settings'));
  }
  return response.json();
}

async function fetchCenProfiles(token?: string) {
  const response = await apiFetch('/api/v1/admin/settings/cen-profiles', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch CEN profile settings'));
  }
  return response.json();
}

async function updateDataCarrierComplianceSettings(
  payload: DataCarrierComplianceSettingsResponse,
  token?: string
) {
  const response = await apiFetch(
    '/api/v1/admin/settings/data-carrier-compliance',
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    token
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to update data carrier settings'));
  }
  return response.json();
}

function validateBaseUri(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return 'Base URI is required.';
  if (!/^https?:\/\//i.test(trimmed)) return 'Base URI must start with http:// or https://';
  if (!trimmed.endsWith('/')) return 'Base URI must end with /.';
  if (trimmed.includes('?') || trimmed.includes('#')) {
    return 'Base URI must not include query or fragment.';
  }
  return null;
}

export default function GlobalIdSettingsPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const queryClient = useQueryClient();
  const [value, setValue] = useState('');
  const [touched, setTouched] = useState(false);
  const [carrierDraft, setCarrierDraft] = useState<DataCarrierComplianceSettingsResponse | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<GlobalIdSettingsResponse>({
    queryKey: ['settings', 'global-asset-id-base-uri'],
    queryFn: () => fetchGlobalAssetIdBaseUri(token),
    enabled: Boolean(token),
  });

  const carrierSettingsQuery = useQuery<DataCarrierComplianceSettingsResponse>({
    queryKey: ['settings', 'data-carrier-compliance'],
    queryFn: () => fetchDataCarrierComplianceSettings(token),
    enabled: Boolean(token),
  });
  const cenProfilesQuery = useQuery<CENProfileDiagnosticsResponse>({
    queryKey: ['settings', 'cen-profiles'],
    queryFn: () => fetchCenProfiles(token),
    enabled: Boolean(token),
  });

  useEffect(() => {
    if (data?.global_asset_id_base_uri) {
      setValue(data.global_asset_id_base_uri);
    }
  }, [data?.global_asset_id_base_uri]);

  useEffect(() => {
    if (carrierSettingsQuery.data) {
      setCarrierDraft(carrierSettingsQuery.data);
    }
  }, [carrierSettingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (nextValue: string) => updateGlobalAssetIdBaseUri(nextValue, token),
    onSuccess: (updated: GlobalIdSettingsResponse) => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'global-asset-id-base-uri'] });
      setValue(updated.global_asset_id_base_uri);
      setTouched(false);
    },
  });

  const carrierMutation = useMutation({
    mutationFn: (payload: DataCarrierComplianceSettingsResponse) =>
      updateDataCarrierComplianceSettings(payload, token),
    onSuccess: (updated: DataCarrierComplianceSettingsResponse) => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'data-carrier-compliance'] });
      setCarrierDraft(updated);
    },
  });

  const validationError = useMemo(() => validateBaseUri(value), [value]);
  const canSubmit = !validationError && !mutation.isPending;
  const previewSuffix = 'PART-123--SN-456--BATCH-789';

  if (isError) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Unable to load settings</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {(error as Error)?.message || 'Something went wrong.'}
        </p>
        <div className="mt-4 flex gap-3">
          <Button
            onClick={() => auth.signinRedirect()}
          >
            Sign in again
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['settings', 'global-asset-id-base-uri'] })
            }
          >
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Identifier Settings"
        description="Configure the base URI used for global asset identifiers."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Global Asset ID Base URI</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                setTouched(true);
                if (!validationError) {
                  mutation.mutate(value.trim());
                }
              }}
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="base-uri">Base URI</Label>
                <Input
                  id="base-uri"
                  type="text"
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  onBlur={() => setTouched(true)}
                  placeholder="http://example.org/asset/"
                />
                {touched && validationError && (
                  <p className="text-sm text-destructive">{validationError}</p>
                )}
                {!validationError && (
                  <p className="text-xs text-muted-foreground">
                    Must start with http:// or https://, end with /, and contain no query or
                    fragment.
                  </p>
                )}
                {cenProfilesQuery.data?.enabled && value.trim().startsWith('http://') && (
                  <Alert className="border-amber-300 bg-amber-50">
                    <AlertDescription>
                      CEN profiles default to HTTPS canonical identifiers. HTTP may be rejected
                      unless backend `cen_allow_http_identifiers` is enabled.
                    </AlertDescription>
                  </Alert>
                )}
              </div>

              <Alert>
                <AlertTitle className="text-sm">Preview</AlertTitle>
                <AlertDescription>
                  <div className="mt-1 text-xs font-mono">
                    {value.trim() ? `${value.trim()}${previewSuffix}` : `http://example.org/asset/${previewSuffix}`}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Composite suffix uses manufacturerPartId, serialNumber, and batchId when present.
                  </div>
                </AlertDescription>
              </Alert>

              {cenProfilesQuery.data && (
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertTitle className="text-sm">Active CEN Profile</AlertTitle>
                  <AlertDescription className="text-xs">
                    {cenProfilesQuery.data.standards_header}
                  </AlertDescription>
                </Alert>
              )}

              {mutation.isError && (
                <ErrorBanner
                  message={(mutation.error as Error)?.message || 'Failed to update settings.'}
                />
              )}
              {mutation.isSuccess && !mutation.isPending && (
                <Alert className="border-green-200 bg-green-50 text-green-700">
                  <AlertDescription>Settings updated successfully.</AlertDescription>
                </Alert>
              )}

              <div className="flex justify-end">
                <Button type="submit" disabled={!canSubmit}>
                  {mutation.isPending ? 'Saving...' : 'Save changes'}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Data Carrier Compliance Profile</CardTitle>
        </CardHeader>
        <CardContent>
          {carrierSettingsQuery.isLoading || !carrierDraft ? (
            <LoadingSpinner size="sm" />
          ) : (
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                carrierMutation.mutate(carrierDraft);
              }}
            >
              <div className="flex items-center gap-3">
                <Switch
                  id="carrier-gate-enabled"
                  checked={carrierDraft.publish_gate_enabled}
                  onCheckedChange={(checked) =>
                    setCarrierDraft((current) =>
                      current ? { ...current, publish_gate_enabled: checked } : current
                    )
                  }
                />
                <Label htmlFor="carrier-gate-enabled">Enable carrier gate before publish</Label>
              </div>

              <div className="space-y-2">
                <Label htmlFor="carrier-profile-name">Profile name</Label>
                <Input
                  id="carrier-profile-name"
                  value={carrierDraft.profile.name}
                  onChange={(event) =>
                    setCarrierDraft((current) =>
                      current
                        ? {
                            ...current,
                            profile: { ...current.profile, name: event.target.value },
                          }
                        : current
                    )
                  }
                />
              </div>

              <div className="space-y-2">
                <Label>Allowed carrier types</Label>
                <div className="flex flex-wrap gap-4">
                  {(['qr', 'datamatrix', 'nfc'] as const).map((carrierType) => (
                    <label key={carrierType} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={carrierDraft.profile.allowed_carrier_types.includes(carrierType)}
                        onChange={(event) => {
                          const next = new Set(carrierDraft.profile.allowed_carrier_types);
                          if (event.target.checked) {
                            next.add(carrierType);
                          } else {
                            next.delete(carrierType);
                          }
                          setCarrierDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  profile: {
                                    ...current.profile,
                                    allowed_carrier_types: Array.from(next),
                                  },
                                }
                              : current
                          );
                        }}
                      />
                      {carrierType}
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="flex items-center gap-3">
                  <Switch
                    id="carrier-require-active"
                    checked={carrierDraft.profile.publish_require_active_carrier}
                    onCheckedChange={(checked) =>
                      setCarrierDraft((current) =>
                        current
                          ? {
                              ...current,
                              profile: { ...current.profile, publish_require_active_carrier: checked },
                            }
                          : current
                      )
                    }
                  />
                  <Label htmlFor="carrier-require-active">Require active carrier</Label>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id="carrier-enforce-gtin"
                    checked={carrierDraft.profile.enforce_gtin_verified}
                    onCheckedChange={(checked) =>
                      setCarrierDraft((current) =>
                        current
                          ? {
                              ...current,
                              profile: { ...current.profile, enforce_gtin_verified: checked },
                            }
                          : current
                      )
                    }
                  />
                  <Label htmlFor="carrier-enforce-gtin">Require GTIN verification for GS1</Label>
                </div>
              </div>

              {carrierMutation.isError && (
                <ErrorBanner
                  message={(carrierMutation.error as Error)?.message || 'Failed to update data carrier settings.'}
                />
              )}
              {carrierMutation.isSuccess && !carrierMutation.isPending && (
                <Alert className="border-green-200 bg-green-50 text-green-700">
                  <AlertDescription>Data carrier settings updated successfully.</AlertDescription>
                </Alert>
              )}

              <div className="flex justify-end">
                <Button type="submit" disabled={carrierMutation.isPending}>
                  {carrierMutation.isPending ? 'Saving...' : 'Save carrier settings'}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
