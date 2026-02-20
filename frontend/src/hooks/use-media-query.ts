'use client';

import { useState, useEffect } from 'react';

/**
 * Hook for responsive design using media queries
 * @param query - CSS media query string (e.g., '(min-width: 768px)')
 * @returns boolean indicating if the media query matches
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);

    // Set initial value
    setMatches(media.matches);

    // Create event listener
    const listener = (e: MediaQueryListEvent) => {
      setMatches(e.matches);
    };

    // Add listener (with fallback for older browsers)
    if (media.addEventListener) {
      media.addEventListener('change', listener);
    } else {
      // Fallback for older Safari versions
      media.addListener(listener);
    }

    // Cleanup
    return () => {
      if (media.removeEventListener) {
        media.removeEventListener('change', listener);
      } else {
        media.removeListener(listener);
      }
    };
  }, [query]);

  return matches;
}

/**
 * Predefined breakpoints matching Tailwind's default breakpoints
 */
export const breakpoints = {
  sm: '(min-width: 640px)',
  md: '(min-width: 768px)',
  lg: '(min-width: 1024px)',
  xl: '(min-width: 1280px)',
  '2xl': '(min-width: 1536px)',
} as const;

/**
 * Hook for checking if the viewport is mobile (below md breakpoint)
 */
export function useIsMobile(): boolean {
  return !useMediaQuery(breakpoints.md);
}

/**
 * Hook for checking if the viewport is tablet or larger
 */
export function useIsTabletOrLarger(): boolean {
  return useMediaQuery(breakpoints.md);
}
