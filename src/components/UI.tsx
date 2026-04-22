import { ReactNode } from 'react';

export function Card({ title, right, children }: { title?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-[28px] border border-[var(--border-soft)] bg-[var(--bg-surface)] p-5 shadow-[var(--shadow-card)] backdrop-blur sm:p-6">
      {(title || right) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title ? <h3 className="text-base font-semibold text-[var(--text-main)] sm:text-lg">{title}</h3> : <span />}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Button({ children, className = '', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_10px_20px_rgba(47,111,237,0.18)] transition hover:bg-[var(--brand-strong)] disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm text-[var(--text-main)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--brand)] focus:ring-4 focus:ring-[rgba(47,111,237,0.12)]"
    />
  );
}
