import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { PublicSmtIssue, PublicSmtIssueType } from '../lib/publicSmtErrors';

type ValidationIssuesPanelProps = {
  title: string;
  issues: PublicSmtIssue[];
  onIssueClick?: (issue: PublicSmtIssue) => void;
  className?: string;
};

const issueTypeLabel: Record<PublicSmtIssueType, string> = {
  schema: 'Schema',
  metamodel: 'Metamodel',
  instance: 'Instance',
  warning: 'Warnings',
  unknown: 'Other',
};

function issueSummary(issues: PublicSmtIssue[]): Array<{ type: PublicSmtIssueType; count: number }> {
  const counts = new Map<PublicSmtIssueType, number>();
  for (const issue of issues) {
    counts.set(issue.type, (counts.get(issue.type) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count);
}

function issueText(issue: PublicSmtIssue): string {
  if (issue.path === 'root') return issue.message;
  return `${issue.path}: ${issue.message}`;
}

export function ValidationIssuesPanel({
  title,
  issues,
  onIssueClick,
  className,
}: ValidationIssuesPanelProps) {
  if (issues.length === 0) return null;

  const summary = issueSummary(issues);

  return (
    <section
      aria-label={title}
      className={cn('rounded-md border border-destructive/40 bg-destructive/5 p-3', className)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        <Badge variant="destructive">{issues.length}</Badge>
        {summary.map((entry) => (
          <Badge key={entry.type} variant="outline" className="text-[11px]">
            {issueTypeLabel[entry.type]}: {entry.count}
          </Badge>
        ))}
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {issues.map((issue, index) => {
          const key = `${issue.type}-${issue.path}-${issue.message}-${index}`;
          const clickable = Boolean(onIssueClick && issue.path !== 'root');
          return (
            <li key={key}>
              {clickable ? (
                <button
                  type="button"
                  className="text-left underline hover:no-underline"
                  onClick={() => onIssueClick?.(issue)}
                >
                  {issueText(issue)}
                </button>
              ) : (
                <span>{issueText(issue)}</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
