import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/status-badge';
import { Card, CardContent } from '@/components/ui/card';
import { Link2, Copy, Check } from 'lucide-react';
import { fetchDigitalLink } from '@/features/opcua/lib/opcuaApi';

interface DPPHeaderProps {
  productName: string;
  dppId: string;
  status: string;
  assetIds?: Record<string, unknown>;
}

export function DPPHeader({ productName, dppId, status, assetIds }: DPPHeaderProps) {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const hasGtin = !!assetIds?.gtin;
  const [copied, setCopied] = useState(false);

  const { data: digitalLink } = useQuery({
    queryKey: ['digital-link', dppId],
    queryFn: () => fetchDigitalLink(token!, dppId),
    enabled: !!token && hasGtin,
  });

  function handleCopy(uri: string) {
    void navigator.clipboard.writeText(uri);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

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
        {digitalLink && (
          <div className="mt-3 flex items-center gap-2">
            <Badge variant="outline" className="bg-green-50 text-green-800 border-green-200">
              <Link2 className="h-3 w-3 mr-1" />
              GS1 Digital Link
              {digitalLink.is_pseudo_gtin && (
                <span className="ml-1 text-xs text-muted-foreground">(pseudo)</span>
              )}
            </Badge>
            <a
              href={digitalLink.digital_link_uri}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono text-primary hover:underline truncate max-w-[300px]"
            >
              {digitalLink.digital_link_uri}
            </a>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => handleCopy(digitalLink.digital_link_uri)}
            >
              {copied ? (
                <Check className="h-3 w-3 text-green-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
