import { useParams, Link } from 'react-router-dom';
import { useProjectDetail } from '@/hooks/useProjectDetail';
import { useProjectStatus } from '@/hooks/useProjectStatus';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Eye,
  Wifi,
} from 'lucide-react';
import { AGENT_LABELS, AGENT_ORDER, AGENT_TO_FIELD } from '@/lib/types';

const statusBadge = (status: string) => {
  switch (status) {
    case 'completed':
      return (
        <Badge variant="success">
          <CheckCircle2 className="h-3 w-3 mr-1" /> Completed
        </Badge>
      );
    case 'running':
    case 'refining':
      return (
        <Badge variant="info">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" /> {status}
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="destructive">
          <XCircle className="h-3 w-3 mr-1" /> Failed
        </Badge>
      );
    default:
      return (
        <Badge variant="warning">
          <Clock className="h-3 w-3 mr-1" /> {status}
        </Badge>
      );
  }
};

const artifactStatus = (val: unknown) =>
  val != null ? (
    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  ) : (
    <Clock className="h-4 w-4 text-muted-foreground" />
  );

export default function MonitorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: detail, isLoading: detailLoading } = useProjectDetail(projectId);
  const { data: status } = useProjectStatus(projectId);

  if (detailLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">Project not found.</p>
        <Button asChild variant="link" className="mt-2">
          <Link to="/">Back to Dashboard</Link>
        </Button>
      </div>
    );
  }

  const isActive = detail.status === 'running' || detail.status === 'pending' || detail.status === 'refining';

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Generation Monitor
          </h1>
          <p className="text-sm text-muted-foreground mt-1 break-all font-mono">
            {detail.id}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {statusBadge(detail.status)}
          {detail.status === 'completed' && (
            <Button asChild>
              <Link to={`/projects/${detail.id}`}>
                <Eye className="h-4 w-4 mr-1" /> View Results
              </Link>
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {AGENT_ORDER.map((agent) => {
          const label = AGENT_LABELS[agent];
          const field = AGENT_TO_FIELD[agent];
          const generated = detail[field] != null;
          const Icon = generated ? CheckCircle2 : isActive ? Loader2 : Clock;

          return (
            <Card key={agent}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium">
                    {label}
                  </CardTitle>
                  <Icon
                    className={`h-4 w-4 ${
                      generated
                        ? 'text-emerald-500'
                        : isActive
                          ? 'animate-spin text-blue-500'
                          : 'text-muted-foreground'
                    }`}
                  />
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground capitalize">
                  {generated ? 'completed' : isActive ? 'in progress...' : 'pending'}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {isActive && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
            <Wifi className="h-4 w-4 text-blue-400" />
            <p className="text-sm text-muted-foreground">
              Generation in progress. Receiving live updates.
            </p>
          </CardContent>
        </Card>
      )}

      {detail.status === 'completed' && (
        <Card>
          <CardHeader>
            <CardTitle>Artifacts Generated</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ['requirements', 'Requirements'],
                ['architecture', 'Architecture'],
                ['source_code', 'Source Code'],
                ['test_suite', 'Tests'],
                ['review_report', 'Review'],
                ['documentation', 'Documentation'],
              ].map(([key, label]) => (
                <div
                  key={key}
                  className="flex items-center gap-2 text-sm"
                >
                  {artifactStatus(detail[key as keyof typeof detail])}
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {status && (
        <>
          <Separator />
          <div className="text-xs text-muted-foreground space-y-1">
            <p>Created: {new Date(status.created_at).toLocaleString()}</p>
            <p>Updated: {new Date(status.updated_at).toLocaleString()}</p>
            {status.completed_at && (
              <p>
                Completed: {new Date(status.completed_at).toLocaleString()}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
