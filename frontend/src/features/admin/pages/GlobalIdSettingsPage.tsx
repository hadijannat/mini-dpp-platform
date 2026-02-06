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
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

type GlobalIdSettingsResponse = {
  global_asset_id_base_uri: string;
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

function validateBaseUri(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return 'Base URI is required.';
  if (!trimmed.startsWith('http://')) return 'Base URI must start with http://';
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

  useEffect(() => {
    if (data?.global_asset_id_base_uri) {
      setValue(data.global_asset_id_base_uri);
    }
  }, [data?.global_asset_id_base_uri]);

  const mutation = useMutation({
    mutationFn: (nextValue: string) => updateGlobalAssetIdBaseUri(nextValue, token),
    onSuccess: (updated: GlobalIdSettingsResponse) => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'global-asset-id-base-uri'] });
      setValue(updated.global_asset_id_base_uri);
      setTouched(false);
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
                    Must start with http://, end with /, and contain no query or fragment.
                  </p>
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
    </div>
  );
}
