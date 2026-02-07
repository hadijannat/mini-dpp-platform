import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

type FormToolbarProps = {
  onSave: () => void;
  onReset: () => void;
  onRebuild: () => void;
  isSaving: boolean;
};

export function FormToolbar({
  onSave,
  onReset,
  onRebuild,
  isSaving,
}: FormToolbarProps) {
  return (
    <div className="flex justify-end gap-3">
      <Button variant="outline" onClick={onReset}>
        Reset
      </Button>
      {!isSaving && (
        <Button variant="ghost" onClick={onRebuild}>
          Rebuild from template
        </Button>
      )}
      <Button onClick={onSave} disabled={isSaving}>
        {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        {isSaving ? 'Saving...' : 'Save Changes'}
      </Button>
    </div>
  );
}
