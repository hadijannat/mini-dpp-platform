import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { DataField } from './DataField';

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
            <dl className="grid gap-3 sm:grid-cols-2 p-2">
              {((submodel.submodelElements || []) as Array<Record<string, unknown>>).map(
                (el, idx) => (
                  <DataField key={idx} label={el.idShort as string} value={el.value} />
                ),
              )}
            </dl>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
