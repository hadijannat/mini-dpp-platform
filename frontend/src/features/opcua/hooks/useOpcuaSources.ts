import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  fetchSources,
  fetchSource,
  createSource,
  updateSource,
  deleteSource,
  testSourceConnection,
  type OPCUASourceCreateInput,
  type OPCUASourceUpdateInput,
} from '../lib/opcuaApi';

export function useOpcuaSources(offset = 0, limit = 50) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-sources', offset, limit],
    queryFn: () => fetchSources(token, { offset, limit }),
    enabled: !!token,
  });
}

export function useOpcuaSource(sourceId: string | undefined) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-source', sourceId],
    queryFn: () => fetchSource(token, sourceId!),
    enabled: !!token && !!sourceId,
  });
}

export function useCreateSource() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OPCUASourceCreateInput) => createSource(token, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-sources'] });
    },
  });
}

export function useUpdateSource() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sourceId, data }: { sourceId: string; data: OPCUASourceUpdateInput }) =>
      updateSource(token, sourceId, data),
    onSuccess: (_res, { sourceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-sources'] });
      void queryClient.invalidateQueries({ queryKey: ['opcua-source', sourceId] });
    },
  });
}

export function useDeleteSource() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) => deleteSource(token, sourceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-sources'] });
    },
  });
}

export function useTestConnection() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useMutation({
    mutationFn: (sourceId: string) => testSourceConnection(token, sourceId),
  });
}
