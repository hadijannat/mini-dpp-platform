import { useQuery } from '@tanstack/react-query';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import {
  loadGeneratedCirpassManifest,
  parseCirpassLabManifest,
} from '../schema/manifestLoader';
import type { CirpassLabManifest } from '../schema/storySchema';

export interface ResolvedCirpassManifest {
  manifest: CirpassLabManifest;
  resolved_from: 'api' | 'generated';
  warning?: string;
}

async function fetchCirpassManifestLatest(): Promise<ResolvedCirpassManifest> {
  try {
    const response = await apiFetch('/api/v1/public/cirpass/lab/manifest/latest');
    if (!response.ok) {
      throw new Error(await getApiErrorMessage(response, 'Unable to load CIRPASS lab manifest.'));
    }

    const payload = (await response.json()) as unknown;
    return {
      manifest: parseCirpassLabManifest(payload),
      resolved_from: 'api',
    };
  } catch {
    return {
      manifest: loadGeneratedCirpassManifest(),
      resolved_from: 'generated',
      warning: 'Scenario manifest service unavailable. Running bundled manifest.',
    };
  }
}

export function useCirpassManifest() {
  return useQuery<ResolvedCirpassManifest>({
    queryKey: ['cirpass-lab-manifest-latest'],
    queryFn: fetchCirpassManifestLatest,
    staleTime: 60_000,
    retry: 1,
    refetchInterval: 300_000,
  });
}
