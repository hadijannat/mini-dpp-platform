import { type LucideIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface FeatureCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  iconClassName?: string;
}

export default function FeatureCard({
  icon: Icon,
  title,
  description,
  iconClassName,
}: FeatureCardProps) {
  return (
    <Card className="transition-all duration-200 hover:shadow-md hover:border-primary/20">
      <CardContent className="pt-6">
        <div
          className={cn(
            'mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary',
            iconClassName,
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="mb-2 font-semibold">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
