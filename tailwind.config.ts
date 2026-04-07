import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        operum: {
          bg: '#F2F2F2',
          text: '#252525',
          dark: '#3E3E3E',
          midDark: '#717171',
          midLight: '#A5A5A5',
          blue: '#3D4D9C',
          pink: '#C7559B',
          purple: '#E15EF2',
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
