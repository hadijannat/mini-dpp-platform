import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

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
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900">Unable to load settings</h2>
        <p className="mt-2 text-sm text-gray-600">
          {(error as Error)?.message || 'Something went wrong.'}
        </p>
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            onClick={() => auth.signinRedirect()}
            className="px-4 py-2 rounded-md text-sm text-white bg-primary-600 hover:bg-primary-700"
          >
            Sign in again
          </button>
          <button
            type="button"
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['settings', 'global-asset-id-base-uri'] })
            }
            className="px-4 py-2 rounded-md text-sm text-gray-700 border border-gray-300 hover:bg-gray-50"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Identifier Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure the base URI used for global asset identifiers.
        </p>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        {isLoading ? (
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-500" />
            Loading settings...
          </div>
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
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Global Asset ID Base URI
              </label>
              <input
                type="text"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onBlur={() => setTouched(true)}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                placeholder="http://example.org/asset/"
              />
              {touched && validationError && (
                <p className="mt-2 text-sm text-red-600">{validationError}</p>
              )}
              {!validationError && (
                <p className="mt-2 text-xs text-gray-500">
                  Must start with http://, end with /, and contain no query or fragment.
                </p>
              )}
            </div>

            <div className="rounded-md border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
              <div className="font-medium text-gray-600">Preview</div>
              <div className="mt-1">
                {value.trim() ? `${value.trim()}${previewSuffix}` : `http://example.org/asset/${previewSuffix}`}
              </div>
              <div className="mt-1 text-gray-500">
                Composite suffix uses manufacturerPartId, serialNumber, and batchId when present.
              </div>
            </div>

            {mutation.isError && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {(mutation.error as Error)?.message || 'Failed to update settings.'}
              </div>
            )}
            {mutation.isSuccess && !mutation.isPending && (
              <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                Settings updated successfully.
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={!canSubmit}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
              >
                {mutation.isPending ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
