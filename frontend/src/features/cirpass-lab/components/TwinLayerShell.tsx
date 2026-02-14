import { type ReactNode, useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Button } from '@/components/ui/button';

type LayerKind = 'joyful' | 'technical';

interface TwinLayerShellProps {
  layer: LayerKind;
  onToggleLayer: () => void;
  joyfulView: ReactNode;
  technicalView: ReactNode;
}

export default function TwinLayerShell({
  layer,
  onToggleLayer,
  joyfulView,
  technicalView,
}: TwinLayerShellProps) {
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code !== 'Space') {
        return;
      }

      const target = event.target as HTMLElement | null;
      const isTypingTarget =
        !!target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (isTypingTarget) {
        return;
      }

      event.preventDefault();
      onToggleLayer();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onToggleLayer]);

  return (
    <div className="relative overflow-hidden rounded-3xl border border-landing-ink/15 bg-slate-950 p-4 shadow-[0_30px_70px_-40px_rgba(0,0,0,0.8)]">
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(900px 420px at 6% 5%, rgba(67, 158, 188, 0.23), transparent 62%), radial-gradient(620px 420px at 96% 100%, rgba(232, 171, 59, 0.25), transparent 72%), linear-gradient(180deg, #05070b 0%, #111827 100%)',
        }}
      />

      <div className="relative z-10">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.13em] text-slate-300">
            Twin-Layer Simulator
          </p>
          <Button
            type="button"
            variant="outline"
            className="h-9 rounded-full border-white/20 bg-white/5 px-4 text-xs font-semibold uppercase tracking-[0.12em] text-white hover:bg-white/15"
            onClick={onToggleLayer}
            data-testid="cirpass-layer-toggle"
          >
            Switch to {layer === 'joyful' ? 'Technical' : 'Joyful'}
          </Button>
        </div>

        <div className="relative min-h-[420px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60">
          {shouldReduceMotion ? (
            <div className="h-full">{layer === 'joyful' ? joyfulView : technicalView}</div>
          ) : (
            <AnimatePresence mode="wait" initial={false}>
              {layer === 'joyful' ? (
                <motion.div
                  key="joyful"
                  initial={{ opacity: 0, rotateY: -12, x: -24 }}
                  animate={{ opacity: 1, rotateY: 0, x: 0 }}
                  exit={{ opacity: 0, rotateY: 12, x: 24 }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="h-full"
                  data-testid="cirpass-layer-joyful"
                >
                  {joyfulView}
                </motion.div>
              ) : (
                <motion.div
                  key="technical"
                  initial={{ opacity: 0, rotateY: 12, x: 24 }}
                  animate={{ opacity: 1, rotateY: 0, x: 0 }}
                  exit={{ opacity: 0, rotateY: -12, x: -24 }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="h-full"
                  data-testid="cirpass-layer-technical"
                >
                  {technicalView}
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>

        <p className="mt-3 text-center text-xs font-medium text-slate-300">
          Press <kbd className="rounded bg-white px-1.5 py-0.5 font-mono text-black">Space</kbd> to
          flip dimensions.
        </p>
      </div>
    </div>
  );
}
