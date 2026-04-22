import { Menu, LayoutDashboard, Newspaper, MessageCircle, BriefcaseBusiness, Settings, LogOut, ChevronRight, ChartNoAxesCombined } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { ALL_PORTFOLIOS_ID, getPortfolioLabel } from '../utils/portfolios';

const nav = [
  { to: '/', label: 'Visão geral', helper: 'Resumo simples da sua carteira', icon: LayoutDashboard },
  { to: '/dashboard-tecnico', label: 'Painel técnico', helper: 'Análises e gráficos detalhados', icon: ChartNoAxesCombined },
  { to: '/noticias', label: 'Notícias', helper: 'O que pode mexer com seus investimentos', icon: Newspaper },
  { to: '/chat', label: 'Chat', helper: 'Tire dúvidas em linguagem simples', icon: MessageCircle },
  { to: '/carteiras', label: 'Carteiras', helper: 'Monte, importe e acompanhe', icon: BriefcaseBusiness },
  { to: '/configuracoes', label: 'Configurações', helper: 'Preferências da sua conta', icon: Settings },
];

export function AppShell() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const { portfolios, activePortfolioId, setActivePortfolioId } = usePortfolios();

  return (
    <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-main)]">
      <div className="flex w-full">
        <aside className={`fixed left-0 top-0 z-30 h-screen w-80 border-r border-[rgba(255,255,255,0.12)] bg-[#252525] p-6 text-white transition ${open ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
          <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.22em] text-white/60">Operum</p>
            <p className="mt-3 text-sm leading-6 text-white/72">Seu futuro mais claro.</p>
          </div>

          <nav className="mt-6 space-y-2">
            {nav.map(({ to, label, helper, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-start gap-3 rounded-2xl px-4 py-3 text-sm transition ${
                    isActive ? 'bg-white text-[#252525] shadow-[0_12px_24px_rgba(37,37,37,0.2)]' : 'hover:bg-white/10'
                  }`
                }
              >
                <Icon size={18} className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{label}</p>
                  <p className="mt-1 text-xs leading-5 opacity-75">{helper}</p>
                </div>
                <ChevronRight size={16} className="mt-1 shrink-0 opacity-60" />
              </NavLink>
            ))}
          </nav>

          <div className="mt-8 rounded-[24px] border border-white/10 bg-white/5 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-white/50">Conta</p>
                <p className="mt-2 text-base font-semibold">{user?.name}</p>
                <p className="mt-1 text-sm text-white/68">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                className="rounded-2xl border border-white/12 p-2.5 text-[#E15EF2] transition hover:bg-white/10"
                aria-label="Sair"
                title="Sair"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </aside>

        {open && <button className="fixed inset-0 z-20 bg-black/30 md:hidden" onClick={() => setOpen(false)} />}

        <main className="min-w-0 flex-1 md:ml-80">
          <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border-soft)] bg-[rgba(255,250,242,0.82)] px-4 py-4 backdrop-blur sm:px-8">
            <button className="rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface)] p-3 md:hidden" onClick={() => setOpen(true)}>
              <Menu size={18} />
            </button>
            <div>
              <p className="text-lg font-semibold">Acompanhe, entenda e invista com inteligência.</p>
            </div>
            <div className="min-w-[15rem]">
              <label className="mb-1 block text-right text-[11px] uppercase tracking-[0.16em] text-[var(--text-muted)]">Carteira ativa</label>
              <select
                value={activePortfolioId}
                onChange={(e) => setActivePortfolioId(e.target.value)}
                disabled={!portfolios.length}
                className="w-full rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-surface)] px-4 py-2.5 text-sm font-semibold text-[var(--text-main)]"
              >
                {!portfolios.length && <option value="">Nenhuma carteira</option>}
                {!!portfolios.length && <option value={ALL_PORTFOLIOS_ID}>Todas as carteiras</option>}
                {portfolios.map((portfolio) => (
                  <option key={portfolio.id} value={portfolio.id}>
                    {getPortfolioLabel(portfolio)}
                  </option>
                ))}
              </select>
            </div>
          </header>
          <div className="p-4 sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
