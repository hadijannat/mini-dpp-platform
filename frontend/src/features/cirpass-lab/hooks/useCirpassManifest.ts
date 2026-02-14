import { useQuery } from '@tanstack/react-query';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import { parseCirpassLabManifest } from '../schema/manifestLoader';
import type { CirpassLabManifest } from '../schema/storySchema';

async function fetchCirpassManifestLatest(): Promise<CirpassLabManifest> {
  const response = await apiFetch('/api/v1/public/cirpass/lab/manifest/latest');
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to load CIRPASS lab manifest.'));
  }

  const payload = (await response.json()) as unknown;
  return parseCirpassLabManifest(payload);
}

export function useCirpassManifest() {
  return useQuery<CirpassLabManifest>({
    queryKey: ['cirpass-lab-manifest-latest'],
    queryFn: fetchCirpassManifestLatest,
    staleTime: 60_000,
    retry: 1,
    refetchInterval: 300_000,
  });
}
