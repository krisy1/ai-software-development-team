import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ProjectDetailResponse } from '@/lib/types';
import { useWebSocket } from './useWebSocket';

function getWsUrl(projectId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '';
  if (base) {
    return base.replace(/^http/, 'ws') + `/projects/${projectId}/ws`;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/v1/projects/${projectId}/ws`;
}

export function useProjectDetail(projectId: string | undefined) {
  const queryClient = useQueryClient();

  useWebSocket(projectId ? getWsUrl(projectId) : null, {
    onMessage: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  return useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const { data } = await api.get<ProjectDetailResponse>(
        `/projects/${projectId}`
      );
      return data;
    },
    enabled: !!projectId,
    refetchInterval: 30_000,
  });
}
