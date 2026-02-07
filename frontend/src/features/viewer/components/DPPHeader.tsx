import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/status-badge';
import { Card, CardContent } from '@/components/ui/card';

interface DPPHeaderProps {
  productName: string;
  dppId: string;
  status: string;
  assetIds?: Record<string, unknown>;
}

export function DPPHeader({ productName, dppId, status, assetIds }: DPPHeaderProps) {
  return (
    <Card className="border-none shadow-md bg-gradient-to-r from-primary/5 to-primary/10">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs">EU DPP</Badge>
              <StatusBadge status={status} />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{productName}</h1>
            <p className="mt-1 text-sm text-muted-foreground font-mono">ID: {dppId}</p>
          </div>
        </div>
        {assetIds && Object.keys(assetIds).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {(Object.entries(assetIds) as [string, unknown][]).map(([key, value]) => (
              <div key={key} className="text-sm">
                <span className="text-muted-foreground">{key}: </span>
                <span className="font-medium">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
