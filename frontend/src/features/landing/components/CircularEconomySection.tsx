import { Check, Leaf, Recycle } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import AnimatedSection from './AnimatedSection';

const bulletPoints = [
  'Track materials from extraction to end-of-life',
  'Enable informed recycling and repair decisions',
  'Ensure compliance with EU sustainability goals',
  'Reduce waste through transparent product data',
];

export default function CircularEconomySection() {
  const shouldReduceMotion = useReducedMotion();

  const cardVariants = shouldReduceMotion
    ? undefined
    : ({
        hidden: { opacity: 0, x: 40 },
        show: { opacity: 1, x: 0, transition: { duration: 0.6, ease: 'easeOut' as const } },
      } as const);

  const cardContainer = {
    hidden: {},
    show: {
      transition: { staggerChildren: shouldReduceMotion ? 0 : 0.15 },
    },
  };

  return (
    <AnimatedSection className="scroll-mt-16 px-4 py-24 sm:py-32">
      <div id="circular-economy" className="mx-auto max-w-6xl scroll-mt-16">
        <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
          {/* Left: text content */}
          <div>
            <Badge variant="secondary" className="mb-4 gap-1.5">
              <Leaf className="h-3.5 w-3.5" />
              Sustainability
            </Badge>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Powering the Circular Economy
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Digital Product Passports are a cornerstone of the EU&apos;s
              circular economy strategy, providing the transparency needed to
              make products more sustainable, repairable, and recyclable.
            </p>
            <ul className="mt-6 space-y-3">
              {bulletPoints.map((point) => (
                <li key={point} className="flex items-start gap-3">
                  <Check className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                  <span className="text-muted-foreground">{point}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Right: visual composition */}
          <motion.div
            className="relative flex items-center justify-center"
            variants={cardContainer}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-100px' }}
          >
            {/* Background accent blob */}
            <div
              className="pointer-events-none absolute right-0 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full bg-primary/10 blur-3xl"
              aria-hidden="true"
            />

            <div className="relative w-full max-w-sm space-y-4">
              <motion.div variants={cardVariants}>
                <Card className="border-primary/20 shadow-md">
                  <CardContent className="flex items-center gap-4 pt-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Recycle className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="font-semibold">Full Lifecycle Tracking</p>
                      <p className="text-sm text-muted-foreground">
                        From raw materials to recycling
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              <motion.div variants={cardVariants}>
                <Card className="border-primary/20 shadow-md">
                  <CardContent className="flex items-center gap-4 pt-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Leaf className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="font-semibold">Environmental Transparency</p>
                      <p className="text-sm text-muted-foreground">
                        Carbon footprint & sustainability data
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </AnimatedSection>
  );
}
