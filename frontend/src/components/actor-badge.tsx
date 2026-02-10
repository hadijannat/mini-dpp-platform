interface ActorInfo {
  subject: string;
  display_name?: string | null;
  email_masked?: string | null;
}

interface ActorBadgeProps {
  actor?: ActorInfo | null;
  fallbackSubject?: string | null;
  className?: string;
}

export function ActorBadge({ actor, fallbackSubject, className }: ActorBadgeProps) {
  const subject = actor?.subject || fallbackSubject || 'unknown';
  const display = actor?.display_name?.trim() || subject;
  const subtitle = actor?.email_masked || (display !== subject ? subject : null);

  return (
    <div className={className}>
      <div className="font-medium text-foreground">{display}</div>
      {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
    </div>
  );
}
