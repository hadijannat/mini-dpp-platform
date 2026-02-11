import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

type FormToolbarProps = {
  onSave: () => void;
  onReset: () => void;
  onRebuild: () => void;
  isSaving: boolean;
  canUpdate?: boolean;
  canReset?: boolean;
};

export function FormToolbar({
  onSave,
  onReset,
  onRebuild,
  isSaving,
  canUpdate = true,
  canReset = true,
}: FormToolbarProps) {
  return (
    <div className="flex justify-end gap-3">
      <Button variant="outline" onClick={onReset} disabled={!canUpdate || !canReset || isSaving}>
        Reset
      </Button>
      {!isSaving && canUpdate && (
        <Button variant="ghost" onClick={onRebuild} disabled={!canUpdate}>
          Rebuild from template
        </Button>
      )}
      <Button onClick={onSave} disabled={isSaving || !canUpdate}>
        {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        {isSaving ? 'Saving...' : 'Save Changes'}
      </Button>
    </div>
  );
}
