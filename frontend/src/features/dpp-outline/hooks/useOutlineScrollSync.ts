import { useEffect, useRef } from 'react';

type OutlineScrollSyncOptions = {
  enabled: boolean;
  attribute: 'data-field-path' | 'data-outline-key';
  onActivePathChange: (path: string) => void;
  root?: Element | null;
};

export function useOutlineScrollSync({
  enabled,
  attribute,
  onActivePathChange,
  root = null,
}: OutlineScrollSyncOptions) {
  const lastPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (
      !enabled ||
      typeof window === 'undefined' ||
      typeof IntersectionObserver === 'undefined'
    ) {
      return;
    }

    const selector = `[${attribute}]`;
    const elements = Array.from(
      document.querySelectorAll<HTMLElement>(selector),
    );

    if (elements.length === 0) return;

    const visible = new Map<Element, IntersectionObserverEntry>();

    const resolveActive = () => {
      const entries = Array.from(visible.values()).filter((entry) => entry.isIntersecting);
      if (entries.length === 0) return;

      const topAligned = entries.sort((left, right) => {
        const topDelta = Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top);
        if (topDelta !== 0) return topDelta;
        return right.intersectionRatio - left.intersectionRatio;
      })[0];

      const value = topAligned.target.getAttribute(attribute);
      if (value && value !== lastPathRef.current) {
        lastPathRef.current = value;
        onActivePathChange(value);
      }
    };

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visible.set(entry.target, entry);
          } else {
            visible.delete(entry.target);
          }
        }
        resolveActive();
      },
      {
        root,
        rootMargin: '-22% 0px -60% 0px',
        threshold: [0, 0.1, 0.25, 0.5, 0.75, 1],
      },
    );

    for (const element of elements) {
      observer.observe(element);
    }

    return () => {
      observer.disconnect();
      visible.clear();
    };
  }, [attribute, enabled, onActivePathChange, root]);
}
