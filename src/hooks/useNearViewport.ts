import { useCallback, useEffect, useState } from 'react';

export function useNearViewport(rootMargin = '400px 0px') {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [isNearViewport, setIsNearViewport] = useState(false);
  const ref = useCallback((element: HTMLDivElement | null) => setNode(element), []);

  useEffect(() => {
    if (isNearViewport) return;
    if (typeof IntersectionObserver === 'undefined') {
      setIsNearViewport(true);
      return;
    }
    if (!node) return;

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setIsNearViewport(true);
        observer.disconnect();
      }
    }, { rootMargin });

    observer.observe(node);
    return () => observer.disconnect();
  }, [isNearViewport, node, rootMargin]);

  return { ref, isNearViewport };
}
