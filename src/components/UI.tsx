import { ReactNode } from 'react';

export function Card({ title, right, children, className = '' }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`surface-card rounded-2xl p-5 sm:p-6 ${className}`}>
      {(title || right) && (
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          {title ? <h3 className="text-lg font-semibold text-[var(--text-main)]">{title}</h3> : <span />}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'ai' | 'danger';
};

export function Button({ children, className = '', variant = 'primary', ...props }: ButtonProps) {
  const base = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition duration-200 disabled:cursor-not-allowed disabled:opacity-50';
  const styles = {
    ghost: 'border border-[var(--border-soft)] bg-transparent text-[var(--text-main)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-surface-muted)]',
    primary: 'bg-[#684cf2] text-white shadow-[0_10px_24px_rgba(104,76,242,0.18)] hover:bg-[#4f2cd9] hover:-translate-y-0.5',
    ai: 'bg-[linear-gradient(135deg,#684cf2,#df50f2)] text-white shadow-[0_10px_28px_rgba(223,80,242,0.22)] hover:-translate-y-0.5 hover:shadow-[0_14px_34px_rgba(223,80,242,0.30)]',
    danger: 'border border-[var(--danger-text)] bg-[var(--danger-soft)] text-[var(--danger-text)] hover:-translate-y-0.5',
  }[variant];
  return <button {...props} className={`${base} ${styles} ${className}`}>{children}</button>;
}

const inputStyles = 'w-full min-h-12 border-0 border-b border-[var(--text-muted)] bg-transparent px-1 py-3 text-sm text-[var(--text-main)] outline-none transition placeholder:text-[var(--text-muted)] focus:rounded-lg focus:border focus:border-[var(--accent)] focus:bg-[var(--bg-surface-strong)] focus:px-4 focus:ring-4 focus:ring-[rgba(223,80,242,0.10)]';

export function Input({ className = '', ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputStyles} ${className}`} />;
}

export function Select({ className = '', children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${inputStyles} cursor-pointer ${className}`}>{children}</select>;
}

export function Badge({ children, tone = 'primary' }: { children: ReactNode; tone?: 'primary' | 'accent' | 'neutral' }) {
  const tones = {
    primary: 'bg-[var(--complementary-soft)] text-[var(--brand)]',
    accent: 'bg-[var(--accent-soft)] text-[var(--accent-strong)]',
    neutral: 'bg-[var(--bg-surface-muted)] text-[var(--text-muted)]',
  };
  return <span className={`inline-flex rounded-full px-3 py-1.5 font-data text-[11px] font-semibold uppercase tracking-[0.08em] ${tones[tone]}`}>{children}</span>;
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-muted)] p-8 text-center">
      {icon && <div className="mx-auto mb-4 flex w-fit text-[var(--brand)]">{icon}</div>}
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--text-muted)]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function StatusMessage({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'error' | 'success' }) {
  const styles = tone === 'error' ? 'bg-[var(--danger-soft)] text-[var(--danger-text)]' : tone === 'success' ? 'bg-[var(--success-soft)] text-[var(--success-text)]' : 'bg-[var(--bg-surface-muted)] text-[var(--text-muted)]';
  return <p role={tone === 'error' ? 'alert' : 'status'} className={`rounded-xl px-4 py-3 text-sm leading-6 ${styles}`}>{children}</p>;
}
