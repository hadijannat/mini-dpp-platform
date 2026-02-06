import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ErrorBannerProps {
  message: string;
  showSignIn?: boolean;
  onSignIn?: () => void;
}

export function ErrorBanner({ message, showSignIn, onSignIn }: ErrorBannerProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex items-center gap-2">
        <span>{message}</span>
        {showSignIn && onSignIn && (
          <button
            onClick={onSignIn}
            className="font-medium underline underline-offset-4 hover:no-underline"
          >
            Sign in
          </button>
        )}
      </AlertDescription>
    </Alert>
  );
}
