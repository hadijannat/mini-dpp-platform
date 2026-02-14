import { useMutation } from '@tanstack/react-query';
import type { CirpassLabEventRequest, CirpassLabEventResponse } from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

async function postCirpassLabEvent(payload: CirpassLabEventRequest): Promise<CirpassLabEventResponse> {
  const response = await apiFetch('/api/v1/public/cirpass/lab/events', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Unable to store lab telemetry event.'));
  }

  return (await response.json()) as CirpassLabEventResponse;
}

export function useCirpassLabTelemetry() {
  const mutation = useMutation<CirpassLabEventResponse, Error, CirpassLabEventRequest>({
    mutationFn: postCirpassLabEvent,
  });

  const trackEvent = (payload: CirpassLabEventRequest) => {
    mutation.mutate(payload);
  };

  return {
    trackEvent,
    isPending: mutation.isPending,
    error: mutation.error,
  };
}
