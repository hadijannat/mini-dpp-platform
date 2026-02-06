import { Progress } from '@/components/ui/progress';

interface FormProgressProps {
  filled: number;
  total: number;
}

export function FormProgress({ filled, total }: FormProgressProps) {
  if (total === 0) return null;
  const percentage = Math.round((filled / total) * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Required fields</span>
        <span>{filled}/{total} ({percentage}%)</span>
      </div>
      <Progress value={percentage} className="h-2" />
    </div>
  );
}
