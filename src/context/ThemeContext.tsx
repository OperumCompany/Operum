import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from 'react';
import { storageKeys } from '../utils/storage';

export type Theme = 'light' | 'dark';

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(storageKeys.theme);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  function setTheme(nextTheme: Theme) {
    localStorage.setItem(storageKeys.theme, nextTheme);
    setThemeState(nextTheme);
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const value = useMemo<ThemeContextValue>(() => ({
    theme,
    setTheme,
    toggleTheme: () => setTheme(theme === 'light' ? 'dark' : 'light'),
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
}
