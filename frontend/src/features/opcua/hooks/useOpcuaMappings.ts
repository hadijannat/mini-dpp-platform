import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  fetchMappings,
  fetchMapping,
  createMapping,
  updateMapping,
  deleteMapping,
  validateMapping,
  dryRunMapping,
  type OPCUAMappingCreateInput,
  type OPCUAMappingUpdateInput,
  type OPCUAMappingType,
} from '../lib/opcuaApi';

export function useOpcuaMappings(params?: {
  sourceId?: string;
  mappingType?: OPCUAMappingType;
  isEnabled?: boolean;
  offset?: number;
  limit?: number;
}) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: [
      'opcua-mappings',
      params?.sourceId,
      params?.mappingType,
      params?.isEnabled,
      params?.offset,
      params?.limit,
    ],
    queryFn: () => fetchMappings(token, params),
    enabled: !!token,
  });
}

export function useOpcuaMapping(mappingId: string | undefined) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-mapping', mappingId],
    queryFn: () => fetchMapping(token, mappingId!),
    enabled: !!token && !!mappingId,
  });
}

export function useCreateMapping() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OPCUAMappingCreateInput) => createMapping(token, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-mappings'] });
    },
  });
}

export function useUpdateMapping() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ mappingId, data }: { mappingId: string; data: OPCUAMappingUpdateInput }) =>
      updateMapping(token, mappingId, data),
    onSuccess: (_res, { mappingId }) => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-mappings'] });
      void queryClient.invalidateQueries({ queryKey: ['opcua-mapping', mappingId] });
    },
  });
}

export function useDeleteMapping() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (mappingId: string) => deleteMapping(token, mappingId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-mappings'] });
    },
  });
}

export function useValidateMapping() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useMutation({
    mutationFn: (mappingId: string) => validateMapping(token, mappingId),
  });
}

export function useDryRunMapping() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useMutation({
    mutationFn: ({
      mappingId,
      revisionJson,
    }: {
      mappingId: string;
      revisionJson?: Record<string, unknown>;
    }) => dryRunMapping(token, mappingId, revisionJson),
  });
}
