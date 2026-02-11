import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { SubmodelNodeTree } from '@/features/submodels/components/SubmodelNodeTree';
import { buildSubmodelNodeTree } from '@/features/submodels/utils/treeBuilder';

interface RawSubmodelTreeProps {
  submodels: Array<Record<string, unknown>>;
}

export function RawSubmodelTree({ submodels }: RawSubmodelTreeProps) {
  if (submodels.length === 0) return null;

  return (
    <Accordion type="multiple">
      {submodels.map((submodel, index) => (
        <AccordionItem key={index} value={`raw-${index}`}>
          <AccordionTrigger className="hover:no-underline">
            <div className="flex items-center gap-2">
              <span className="font-medium">{submodel.idShort as string}</span>
              <span className="text-xs text-muted-foreground">{submodel.id as string}</span>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div className="p-2">
              <SubmodelNodeTree root={buildSubmodelNodeTree(submodel)} showSemanticMeta />
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
