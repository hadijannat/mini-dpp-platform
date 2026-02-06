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
      <button
        type="button"
        onClick={onReset}
        className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
      >
        Reset
      </button>
      {!isSaving && (
        <button
          type="button"
          onClick={onRebuild}
          className="px-4 py-2 border border-primary-200 text-primary-700 rounded-md text-sm hover:bg-primary-50"
        >
          Rebuild from template
        </button>
      )}
      <button
        type="button"
        onClick={onSave}
        disabled={isSaving}
        className="px-4 py-2 rounded-md text-sm text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
      >
        {isSaving ? 'Saving\u2026' : 'Save Changes'}
      </button>
    </div>
  );
}
