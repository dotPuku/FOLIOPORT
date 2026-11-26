import { useEffect, useRef, useState } from 'react';

export default function useScrollHeader(scrollContainerRef = null) {
  const [visible, setVisible] = useState(true);
  const previousPosition = useRef(0);

  useEffect(() => {
    const scrollContainer = scrollContainerRef?.current || null;
    const target = scrollContainer || window;
    const readPosition = () => scrollContainer ? scrollContainer.scrollTop : window.scrollY;
    const updateVisibility = () => {
      const position = readPosition();
      const delta = position - previousPosition.current;
      if (position <= 8) setVisible(true);
      else if (Math.abs(delta) >= 4) setVisible(delta < 0);
      previousPosition.current = position;
    };

    target.addEventListener('scroll', updateVisibility, { passive: true });
    return () => target.removeEventListener('scroll', updateVisibility);
  }, [scrollContainerRef]);

  return visible;
}
