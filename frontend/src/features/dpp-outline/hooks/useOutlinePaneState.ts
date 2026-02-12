import { useEffect, useMemo, useState } from 'react';

const MIN_WIDTH = 240;
const MAX_WIDTH = 460;
const DEFAULT_WIDTH = 300;

type OutlineContext = 'editor' | 'submodel' | 'viewer';

function clampWidth(value: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(value)));
}

export function useOutlinePaneState(
  context: OutlineContext,
  options?: { defaultWidth?: number },
) {
  const widthKey = useMemo(() => `dpp.outline.${context}.width`, [context]);
  const collapsedKey = useMemo(() => `dpp.outline.${context}.collapsed`, [context]);
  const defaultWidth = clampWidth(options?.defaultWidth ?? DEFAULT_WIDTH);

  const [width, setWidth] = useState<number>(() => {
    if (typeof window === 'undefined') return defaultWidth;
    const raw = window.localStorage.getItem(widthKey);
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? clampWidth(parsed) : defaultWidth;
  });

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(collapsedKey) === 'true';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(widthKey, String(clampWidth(width)));
  }, [width, widthKey]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(collapsedKey, collapsed ? 'true' : 'false');
  }, [collapsed, collapsedKey]);

  return {
    width,
    setWidth: (value: number) => setWidth(clampWidth(value)),
    collapsed,
    setCollapsed,
    toggleCollapsed: () => setCollapsed((previous) => !previous),
    minWidth: MIN_WIDTH,
    maxWidth: MAX_WIDTH,
  };
}
