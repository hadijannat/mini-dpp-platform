import { useAuth } from 'react-oidc-context';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, ChevronDown, Leaf } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function HeroSection() {
  const auth = useAuth();
  const shouldReduceMotion = useReducedMotion();

  const handleGetStarted = () => auth.signinRedirect();
  const handleExplore = () => {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
  };

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: shouldReduceMotion ? 0 : 0.15 },
    },
  };

  const item = shouldReduceMotion
    ? undefined
    : ({
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' as const } },
      } as const);

  return (
    <section className="relative flex min-h-[calc(100vh-3.5rem)] items-center justify-center overflow-hidden px-4">
      {/* Decorative gradient blob */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/15 blur-3xl"
        aria-hidden="true"
      />

      <motion.div
        className="relative z-10 mx-auto max-w-4xl text-center"
        variants={container}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={item}>
          <Badge variant="secondary" className="mb-6 gap-1.5 px-3 py-1 text-sm">
            <Leaf className="h-3.5 w-3.5" />
            EU ESPR Compliant
          </Badge>
        </motion.div>

        <motion.h1
          variants={item}
          className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl"
        >
          Digital Product Passports
          <br />
          <span className="text-primary">Made Simple</span>
        </motion.h1>

        <motion.p
          variants={item}
          className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl"
        >
          Create, manage, and publish standards-compliant Digital Product Passports
          with full EU ESPR support, Catena-X integration, and AAS interoperability.
        </motion.p>

        <motion.div variants={item} className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <Button size="lg" onClick={handleGetStarted}>
            Get Started
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          <Button size="lg" variant="outline" onClick={handleExplore}>
            Explore Features
            <ChevronDown className="ml-2 h-4 w-4" />
          </Button>
        </motion.div>
      </motion.div>
    </section>
  );
}
