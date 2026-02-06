type FormJsonToggleProps = {
  activeView: 'form' | 'json';
  onViewChange: (view: 'form' | 'json') => void;
  formDisabled?: boolean;
};

export function FormJsonToggle({
  activeView,
  onViewChange,
  formDisabled,
}: FormJsonToggleProps) {
  return (
    <div className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-1 text-xs">
      <button
        type="button"
        className={`px-3 py-1 rounded-md ${
          activeView === 'form' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
        }`}
        onClick={() => onViewChange('form')}
        disabled={formDisabled}
      >
        Form
      </button>
      <button
        type="button"
        className={`px-3 py-1 rounded-md ${
          activeView === 'json' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
        }`}
        onClick={() => onViewChange('json')}
      >
        JSON
      </button>
    </div>
  );
}
