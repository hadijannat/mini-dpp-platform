import { useState } from 'react';
import { Copy, Check, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface IntegrityCardProps {
  digest: string;
}

export function IntegrityCard({ digest }: IntegrityCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(digest);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-4 w-4 text-primary" />
          Integrity
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs text-muted-foreground mb-1">SHA-256 Digest</p>
            <p className="text-xs font-mono break-all bg-muted p-2 rounded">{digest}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="shrink-0"
            aria-label={copied ? 'Digest copied' : 'Copy digest to clipboard'}
            title={copied ? 'Digest copied' : 'Copy digest to clipboard'}
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
