import { Card, CardContent } from '@/components/ui/card';
import { DataField } from './DataField';
import type { ESPRCategory } from '../utils/esprCategories';

interface CategorySectionProps {
  category: ESPRCategory;
  elements: Array<{ submodelIdShort: string; element: Record<string, unknown> }>;
}

export function CategorySection({ category, elements }: CategorySectionProps) {
  if (elements.length === 0) return null;

  const Icon = category.icon;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-primary" />
        <h3 className="font-semibold">{category.label}</h3>
        <span className="text-xs text-muted-foreground">({elements.length} fields)</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {elements.map(({ submodelIdShort, element }, idx) => (
          <Card key={`${submodelIdShort}-${element.idShort as string}-${idx}`} className="shadow-sm">
            <CardContent className="p-4">
              <DataField
                label={element.idShort as string}
                value={element.value}
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                from {submodelIdShort}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
