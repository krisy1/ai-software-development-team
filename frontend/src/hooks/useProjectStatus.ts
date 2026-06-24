import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ProjectStatusResponse } from '@/lib/types';
import { useWebSocket } from './useWebSocket';

function getWsUrl(projectId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '';
  if (base) {
    return base.replace(/^http/, 'ws') + `/projects/${projectId}/ws`;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/v1/projects/${projectId}/ws`;
}

export function useProjectStatus(projectId: string | undefined) {
  const queryClient = useQueryClient();

  useWebSocket(projectId ? getWsUrl(projectId) : null, {
    onMessage: () => {
      queryClient.invalidateQueries({ queryKey: ['project-status', projectId] });
    },
  });

  return useQuery({
    queryKey: ['project-status', projectId],
    queryFn: async () => {
      const { data } = await api.get<ProjectStatusResponse>(
        `/projects/${projectId}/status`
      );
      return data;
    },
    enabled: !!projectId,
    refetchInterval: 30_000,
  });
}
