import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  CirpassLeaderboard,
  CirpassLeaderboardSubmitRequest,
  CirpassLeaderboardSubmitResponse,
} from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

async function fetchCirpassLeaderboard(version: string, limit = 20): Promise<CirpassLeaderboard> {
  const search = new URLSearchParams({ version, limit: String(limit) });
  const response = await apiFetch(`/api/v1/public/cirpass/leaderboard?${search.toString()}`);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to load leaderboard.'));
  }
  return (await response.json()) as CirpassLeaderboard;
}

async function submitCirpassScore(
  payload: CirpassLeaderboardSubmitRequest,
): Promise<CirpassLeaderboardSubmitResponse> {
  const response = await apiFetch('/api/v1/public/cirpass/leaderboard/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to submit score.'));
  }

  return (await response.json()) as CirpassLeaderboardSubmitResponse;
}

export function useCirpassLeaderboard(version: string, limit = 20) {
  const queryClient = useQueryClient();

  const leaderboardQuery = useQuery<CirpassLeaderboard>({
    queryKey: ['cirpass-leaderboard', version, limit],
    queryFn: () => fetchCirpassLeaderboard(version, limit),
    enabled: version.trim().length > 0,
    staleTime: 30_000,
    retry: 1,
  });

  const submitMutation = useMutation<
    CirpassLeaderboardSubmitResponse,
    Error,
    CirpassLeaderboardSubmitRequest
  >({
    mutationFn: submitCirpassScore,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['cirpass-leaderboard', version] });
    },
  });

  return {
    leaderboardQuery,
    submitMutation,
  };
}
