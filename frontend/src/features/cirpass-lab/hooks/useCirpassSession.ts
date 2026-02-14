import { useQuery } from '@tanstack/react-query';
import type { CirpassSession } from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

async function createCirpassSession(): Promise<CirpassSession> {
  const response = await apiFetch('/api/v1/public/cirpass/session', {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to initialize CIRPASS session.'));
  }

  return (await response.json()) as CirpassSession;
}

export function useCirpassSession() {
  return useQuery<CirpassSession>({
    queryKey: ['cirpass-session'],
    queryFn: createCirpassSession,
    staleTime: 30 * 60_000,
    gcTime: 2 * 60 * 60_000,
    retry: 1,
  });
}
