import { useEffect, useRef, useState, type ReactNode } from 'react';

interface DeferredSectionProps {
  children: ReactNode;
  minHeight?: number;
  rootMargin?: string;
}

export default function DeferredSection({
  children,
  minHeight = 360,
  rootMargin = '220px',
}: DeferredSectionProps) {
  const anchorRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (visible || !anchorRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );

    observer.observe(anchorRef.current);
    return () => observer.disconnect();
  }, [rootMargin, visible]);

  return (
    <div ref={anchorRef}>
      {visible ? children : <div style={{ minHeight }} aria-hidden="true" />}
    </div>
  );
}
