import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  fetchNodesets,
  fetchNodeset,
  uploadNodeset,
  downloadNodeset,
  searchNodesetNodes,
  deleteNodeset,
} from '../lib/opcuaApi';

export function useOpcuaNodesets(params?: {
  sourceId?: string;
  offset?: number;
  limit?: number;
}) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-nodesets', params?.sourceId, params?.offset, params?.limit],
    queryFn: () => fetchNodesets(token, params),
    enabled: !!token,
  });
}

export function useOpcuaNodeset(nodesetId: string | undefined) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-nodeset', nodesetId],
    queryFn: () => fetchNodeset(token, nodesetId!),
    enabled: !!token && !!nodesetId,
  });
}

export function useUploadNodeset() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      file,
      sourceId,
      companionSpecName,
      companionSpecVersion,
    }: {
      file: File;
      sourceId?: string;
      companionSpecName?: string;
      companionSpecVersion?: string;
    }) => uploadNodeset(token, file, { sourceId, companionSpecName, companionSpecVersion }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-nodesets'] });
    },
  });
}

export function useDownloadNodeset() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useMutation({
    mutationFn: (nodesetId: string) => downloadNodeset(token, nodesetId),
  });
}

export function useSearchNodesetNodes(
  nodesetId: string | undefined,
  params: { q: string; nodeClass?: string; limit?: number },
) {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';

  return useQuery({
    queryKey: ['opcua-nodeset-nodes', nodesetId, params.q, params.nodeClass, params.limit],
    queryFn: () => searchNodesetNodes(token, nodesetId!, params),
    enabled: !!token && !!nodesetId && params.q.length > 0,
  });
}

export function useDeleteNodeset() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (nodesetId: string) => deleteNodeset(token, nodesetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['opcua-nodesets'] });
    },
  });
}
