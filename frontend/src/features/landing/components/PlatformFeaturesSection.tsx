import { FileEdit, Send, FileDown, QrCode, Network, ShieldCheck } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import AnimatedSection from './AnimatedSection';
import FeatureCard from './FeatureCard';

const features = [
  {
    icon: FileEdit,
    title: 'Create & Edit',
    description:
      'Build Digital Product Passports using IDTA-compliant templates with a guided form editor and real-time validation.',
  },
  {
    icon: Send,
    title: 'Publish & Share',
    description:
      'Publish DPPs with unique URLs and QR codes. Public ESPR-category viewer for consumers and regulators.',
  },
  {
    icon: FileDown,
    title: 'Export AASX',
    description:
      'Generate standards-compliant AASX packages per IDTA Part 5 for interoperability with AAS tooling.',
  },
  {
    icon: QrCode,
    title: 'QR & Data Carriers',
    description:
      'GS1 Digital Link QR codes for physical products, enabling scan-to-view passport access.',
  },
  {
    icon: Network,
    title: 'Catena-X Integration',
    description:
      'Register Digital Twins in the Catena-X Digital Twin Registry for supply chain data sharing.',
  },
  {
    icon: ShieldCheck,
    title: 'Compliance Ready',
    description:
      'EU ESPR categories, CE marking fields, conformity declarations, and audit-ready data exports.',
  },
];

export default function PlatformFeaturesSection() {
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
    <AnimatedSection className="scroll-mt-16 bg-muted/50 px-4 py-24 sm:py-32">
      <div id="features" className="mx-auto max-w-6xl scroll-mt-16">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Platform Capabilities
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            Everything you need to create, manage, and distribute Digital Product
            Passports — from authoring to publication and beyond.
          </p>
        </div>

        <motion.div
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-100px' }}
        >
          {features.map((f) => (
            <motion.div key={f.title} variants={item}>
              <FeatureCard
                icon={f.icon}
                title={f.title}
                description={f.description}
              />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </AnimatedSection>
  );
}
