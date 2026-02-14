import { useQuery } from '@tanstack/react-query';
import type { CirpassStoryFeed } from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

async function fetchCirpassStories(): Promise<CirpassStoryFeed> {
  const response = await apiFetch('/api/v1/public/cirpass/stories/latest');
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, 'Unable to load latest CIRPASS user stories.'),
    );
  }
  return (await response.json()) as CirpassStoryFeed;
}

export function useCirpassStories() {
  return useQuery<CirpassStoryFeed>({
    queryKey: ['cirpass-stories-latest'],
    queryFn: fetchCirpassStories,
    staleTime: 60_000,
    retry: 1,
    refetchInterval: 300_000,
  });
}
