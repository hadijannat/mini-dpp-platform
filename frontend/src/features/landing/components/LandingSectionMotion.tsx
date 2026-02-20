import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface LandingSectionMotionProps {
  children: ReactNode;
  className?: string;
}

const revealTransition = {
  duration: 0.55,
  ease: [0.22, 1, 0.36, 1] as const,
};

export default function LandingSectionMotion({ children, className }: LandingSectionMotionProps) {
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 36 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={revealTransition}
    >
      {children}
    </motion.div>
  );
}
