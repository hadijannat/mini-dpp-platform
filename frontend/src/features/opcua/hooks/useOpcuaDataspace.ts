import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  publishToDataspace,
  fetchPublicationJobs,
  fetchPublicationJob,
  retryPublicationJob,
  type DataspacePublishInput,
} from '../lib/opcuaApi';

export function usePublicationJobs(params?: {
  dppId?: string;
  offset?: number;
  limit?: number;
}) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-dataspace-jobs', params?.dppId, params?.offset, params?.limit],
    queryFn: () => fetchPublicationJobs(token, params),
    enabled: !!token,
  });
}

export function usePublicationJob(jobId: string | undefined) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-dataspace-job', jobId],
    queryFn: () => fetchPublicationJob(token, jobId!),
    enabled: !!token && !!jobId,
  });
}

export function usePublishToDataspace() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DataspacePublishInput) => publishToDataspace(token, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-dataspace-jobs'] });
    },
  });
}

export function useRetryPublicationJob() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => retryPublicationJob(token, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-dataspace-jobs'] });
    },
  });
}
