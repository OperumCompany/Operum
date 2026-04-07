import { ReactNode } from 'react';

export function Card({ title, right, children }: { title?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-[#A5A5A5]/25 bg-white p-4 shadow-sm sm:p-5">
      {(title || right) && (
        <header className="mb-4 flex items-center justify-between">
          {title ? <h3 className="text-sm font-semibold text-[#252525] sm:text-base">{title}</h3> : <span />}
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
      className={`rounded-xl bg-[#3D4D9C] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-xl border border-[#A5A5A5]/50 bg-white px-3 py-2 text-sm text-[#252525] outline-none transition focus:border-[#3D4D9C] focus:ring-2 focus:ring-[#3D4D9C]/20"
    />
  );
}
