export const responsiveBreakpoints = {
  mobile: 640,
  desktop: 1024,
} as const;

export function isDismissKey(key: string) {
  return key === 'Escape';
}
