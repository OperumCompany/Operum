import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const nextLabel = theme === 'light' ? 'Ativar tema escuro' : 'Ativar tema claro';

  return (
    <button type="button" className={`theme-toggle ${className}`} onClick={toggleTheme} aria-label={nextLabel} title={nextLabel}>
      <Sun size={16} className={theme === 'light' ? 'theme-icon-active' : ''} />
      <span className="theme-toggle-track"><span className="theme-toggle-thumb" /></span>
      <Moon size={16} className={theme === 'dark' ? 'theme-icon-active' : ''} />
    </button>
  );
}
