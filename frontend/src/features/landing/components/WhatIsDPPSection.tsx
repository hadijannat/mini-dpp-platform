import { Fingerprint, FlaskConical, Leaf, Recycle } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import AnimatedSection from './AnimatedSection';
import FeatureCard from './FeatureCard';

const cards = [
  {
    icon: Fingerprint,
    title: 'Product Identity',
    description:
      'Unique identification, manufacturer info, serial numbers, and traceability across the supply chain.',
  },
  {
    icon: FlaskConical,
    title: 'Material Composition',
    description:
      'Materials breakdown, substances of concern, recyclate content, and SCIP compliance data.',
  },
  {
    icon: Leaf,
    title: 'Environmental Impact',
    description:
      'Carbon footprint, energy consumption, water usage, and sustainability performance metrics.',
  },
  {
    icon: Recycle,
    title: 'Circular Economy',
    description:
      'End-of-life instructions, repairability scores, recycling pathways, and disassembly guides.',
  },
];

export default function WhatIsDPPSection() {
  const shouldReduceMotion = useReducedMotion();

  const container = {
    hidden: {},
    show: {
      transition: { staggerChildren: shouldReduceMotion ? 0 : 0.1 },
    },
  };

  const item = shouldReduceMotion
    ? undefined
    : ({
        hidden: { opacity: 0, y: 30 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
      } as const);

  return (
    <AnimatedSection className="scroll-mt-16 px-4 py-24 sm:py-32">
      <div id="what-is-dpp" className="mx-auto max-w-6xl scroll-mt-16">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            What is a Digital Product Passport?
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            A structured digital record containing key product information required
            by the EU Ecodesign for Sustainable Products Regulation (ESPR).
          </p>
        </div>

        <motion.div
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-100px' }}
        >
          {cards.map((card) => (
            <motion.div key={card.title} variants={item}>
              <FeatureCard
                icon={card.icon}
                title={card.title}
                description={card.description}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </AnimatedSection>
  );
}
