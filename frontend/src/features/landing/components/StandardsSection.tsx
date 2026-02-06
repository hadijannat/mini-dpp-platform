import { Scale, BookOpen, Box, Network } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import AnimatedSection from './AnimatedSection';

const standards = [
  {
    icon: Scale,
    title: 'EU ESPR',
    badge: 'Regulation',
    description:
      'The Ecodesign for Sustainable Products Regulation establishes the legislative framework requiring Digital Product Passports for products sold in the EU market, starting 2027.',
  },
  {
    icon: BookOpen,
    title: 'IDTA DPP4.0',
    badge: 'Standard',
    description:
      'The Industrial Digital Twin Association specification defines DPP submodel templates and data structures, ensuring interoperable and machine-readable product data.',
  },
  {
    icon: Box,
    title: 'Asset Administration Shell',
    badge: 'Framework',
    description:
      'The AAS provides a standardized, interoperable data model for digital twins and DPP data exchange across organizations, enabling Industry 4.0 integration.',
  },
  {
    icon: Network,
    title: 'Catena-X',
    badge: 'Ecosystem',
    description:
      'The open automotive data ecosystem with Digital Twin Registry integration for supply chain transparency, enabling decentralized data sharing across value chains.',
  },
];

export default function StandardsSection() {
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
      <div id="standards" className="mx-auto max-w-6xl scroll-mt-16">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Built on Industry Standards
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            Full compliance with EU regulations and interoperability with leading
            industry frameworks and ecosystems.
          </p>
        </div>

        <motion.div
          className="grid grid-cols-1 gap-6 sm:grid-cols-2"
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-100px' }}
        >
          {standards.map((s) => (
            <motion.div key={s.title} variants={item}>
              <Card className="h-full transition-all duration-200 hover:shadow-md hover:border-primary/20">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <s.icon className="h-5 w-5" />
                    </div>
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg">{s.title}</CardTitle>
                      <Badge variant="outline" className="text-xs">
                        {s.badge}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm leading-relaxed">
                    {s.description}
                  </CardDescription>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </AnimatedSection>
  );
}
