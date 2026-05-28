import { Card, CardContent } from '@/components/ui/card';
import { DataField } from './DataField';
import { Badge } from '@/components/ui/badge';
import type { ClassifiedNode, ESPRCategory } from '../utils/esprCategories';
import { buildViewerOutlineKey } from '../utils/outlineKey';

interface CategorySectionProps {
  category: ESPRCategory;
  elements: ClassifiedNode[];
  showTechnicalMetadata?: boolean;
}

export function CategorySection({
  category,
  elements,
  showTechnicalMetadata = false,
}: CategorySectionProps) {
  if (elements.length === 0) return null;

  const Icon = category.icon;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-primary" />
        <h2 className="font-semibold">{category.label}</h2>
        <span className="text-xs text-muted-foreground">({elements.length} fields)</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {elements.map((element) => (
          <Card
            key={buildViewerOutlineKey(element)}
            className="shadow-sm"
            data-outline-key={buildViewerOutlineKey(element)}
          >
            <CardContent className="p-4">
              <DataField
                label={element.label}
                value={element.value}
              />
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                <span>Source: {element.submodelIdShort}</span>
                {showTechnicalMetadata && (
                  <>
                    <span aria-hidden>•</span>
                    <span className="break-all">{element.path}</span>
                  </>
                )}
                {showTechnicalMetadata && element.semanticId && (
                  <>
                    <span aria-hidden>•</span>
                    <Badge variant="outline" className="text-[10px]">
                      semantic ID
                    </Badge>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
