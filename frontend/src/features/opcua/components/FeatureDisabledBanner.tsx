import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

export function FeatureDisabledBanner() {
  return (
    <Alert>
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>
        OPC UA integration is not enabled for this environment. Ask your
        administrator to enable the backend flag (<code>OPCUA_ENABLED=true</code>)
        and restart the platform services.
      </AlertDescription>
    </Alert>
  );
}
