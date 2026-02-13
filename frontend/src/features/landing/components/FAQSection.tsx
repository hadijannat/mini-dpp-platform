import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { landingContent } from '../content/landingContent';

export default function FAQSection() {
  return (
    <section id="faq" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-ink/12 bg-white/82 p-6 shadow-[0_24px_48px_-36px_rgba(12,36,49,0.75)] sm:p-8">
        <div className="max-w-3xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            FAQ
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            Common questions from compliance and engineering teams
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
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
