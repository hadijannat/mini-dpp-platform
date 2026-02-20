import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { landingContent } from '../content/landingContent';

export default function FAQSection() {
  return (
    <section id="faq" className="landing-section-spacing scroll-mt-24 px-4 sm:px-6 lg:px-8">
      <div className="landing-container landing-panel-premium p-6 sm:p-8">
        <div className="max-w-3xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            FAQ
          </p>
          <h2 className="landing-section-title mt-3 font-display text-landing-ink">
            Common questions from compliance and engineering teams
          </h2>
          <p className="landing-lead mt-4 text-landing-muted">
            Short answers for the questions that usually come up before technical evaluation and pilot rollout.
          </p>
        </div>

        <Accordion type="single" collapsible className="mt-8">
          {landingContent.faq.map((entry, index) => (
            <AccordionItem key={entry.question} value={`faq-${index}`} className="border-landing-ink/10">
              <AccordionTrigger className="text-left font-semibold text-landing-ink hover:no-underline">
                {entry.question}
              </AccordionTrigger>
              <AccordionContent className="text-sm leading-relaxed text-landing-muted">
                {entry.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
