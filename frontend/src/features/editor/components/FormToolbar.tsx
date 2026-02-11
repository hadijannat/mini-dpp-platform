import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

type FormToolbarProps = {
  onSave: () => void;
  onReset: () => void;
  onRebuild: () => void;
  isSaving: boolean;
  canUpdate?: boolean;
  canReset?: boolean;
  canSave?: boolean;
};

export function FormToolbar({
  onSave,
  onReset,
  onRebuild,
  isSaving,
  canUpdate = true,
  canReset = true,
  canSave = true,
}: FormToolbarProps) {
  return (
    <div className="sticky bottom-0 z-10 flex justify-end gap-3 border-t bg-background/95 px-2 py-3 backdrop-blur sm:static sm:border-0 sm:bg-transparent sm:p-0">
      <Button
        variant="outline"
        className="min-h-11"
        onClick={onReset}
        disabled={!canUpdate || !canReset || isSaving}
      >
        Reset
      </Button>
      {!isSaving && canUpdate && (
        <Button variant="ghost" className="min-h-11" onClick={onRebuild} disabled={!canUpdate}>
          Rebuild from template
        </Button>
      )}
      <Button className="min-h-11" onClick={onSave} disabled={isSaving || !canUpdate || !canSave}>
        {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        {isSaving ? 'Saving...' : 'Save Changes'}
      </Button>
    </div>
  );
}
