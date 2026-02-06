import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
    <Tabs value={activeView} onValueChange={(v) => onViewChange(v as 'form' | 'json')}>
      <TabsList>
        <TabsTrigger value="form" disabled={formDisabled}>Form</TabsTrigger>
        <TabsTrigger value="json">JSON</TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
