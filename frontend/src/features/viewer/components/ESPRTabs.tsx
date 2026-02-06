import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CategorySection } from './CategorySection';
import { ESPR_CATEGORIES } from '../utils/esprCategories';
import { Badge } from '@/components/ui/badge';

interface ESPRTabsProps {
  classified: Record<string, Array<{ submodelIdShort: string; element: Record<string, unknown> }>>;
}

export function ESPRTabs({ classified }: ESPRTabsProps) {
  // Find first non-empty category for default tab
  const defaultTab = ESPR_CATEGORIES.find(c => (classified[c.id]?.length ?? 0) > 0)?.id ?? 'identity';

  return (
    <Tabs defaultValue={defaultTab}>
      <TabsList className="w-full flex-wrap h-auto gap-1 bg-muted/50 p-1">
        {ESPR_CATEGORIES.map(category => {
          const count = classified[category.id]?.length ?? 0;
          const Icon = category.icon;
          return (
            <TabsTrigger key={category.id} value={category.id} className="gap-1.5 text-xs">
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{category.label}</span>
              {count > 0 && <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">{count}</Badge>}
            </TabsTrigger>
          );
        })}
      </TabsList>
      {ESPR_CATEGORIES.map(category => (
        <TabsContent key={category.id} value={category.id} className="mt-4">
          <CategorySection category={category} elements={classified[category.id] ?? []} />
          {(classified[category.id]?.length ?? 0) === 0 && (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No {category.label.toLowerCase()} data available for this product.
            </div>
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}
