import { BriefcaseBusiness, ChartNoAxesCombined, ChevronRight, LayoutDashboard, LogOut, Menu, MessageCircle, Newspaper, PanelLeftClose, PanelLeftOpen, Settings, X } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Brand } from '../components/Brand';
import { ThemeToggle } from '../components/ThemeToggle';
import { Select } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { usePortfolios } from '../context/PortfoliosContext';
import { ALL_PORTFOLIOS_ID, getPortfolioLabel } from '../utils/portfolios';

const nav = [
  { to: '/app', label: 'Visão geral', icon: LayoutDashboard, end: true },
  { to: '/app/dashboard-tecnico', label: 'Painel técnico', icon: ChartNoAxesCombined },
  { to: '/app/noticias', label: 'Notícias', icon: Newspaper },
  { to: '/app/chat', label: 'Chat', icon: MessageCircle },
  { to: '/app/carteiras', label: 'Carteiras', icon: BriefcaseBusiness },
  { to: '/app/configuracoes', label: 'Configurações', icon: Settings },
];

export function AppShell() {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('operum_sidebar_collapsed') === 'true');
  const { user, logout } = useAuth();
  const { portfolios, activePortfolioId, setActivePortfolioId } = usePortfolios();

  function toggleCollapsed() {
    setCollapsed((current) => {
      localStorage.setItem('operum_sidebar_collapsed', String(!current));
      return !current;
    });
  }

  return (
    <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-main)]">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[18rem] flex-col border-r border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-5 shadow-[var(--shadow-float)] transition-[width,padding,transform] duration-200 lg:translate-x-0 lg:shadow-none ${collapsed ? 'lg:w-[5.25rem] lg:px-3' : 'lg:w-[18rem]'} ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className={`flex items-center justify-between ${collapsed ? 'lg:flex-col lg:gap-3' : ''}`}>
          <div className={collapsed ? 'lg:hidden' : ''}><Brand to="/" /></div>
          {collapsed && <div className="hidden lg:block"><Brand compact to="/" /></div>}
          <button type="button" className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-surface-muted)] lg:hidden" onClick={() => setOpen(false)} aria-label="Fechar menu"><X size={20} /></button>
          <button type="button" className="hidden rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-surface-muted)] lg:inline-grid" onClick={toggleCollapsed} aria-label={collapsed ? 'Expandir barra lateral' : 'Recolher barra lateral'} title={collapsed ? 'Expandir barra lateral' : 'Recolher barra lateral'}>{collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}</button>
        </div>

        <nav className="mt-8 flex-1 space-y-2 overflow-y-auto overflow-x-hidden" aria-label="Ferramentas Operum">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setOpen(false)}
              title={collapsed ? label : undefined}
              className={({ isActive }) => `group flex min-h-12 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${collapsed ? 'lg:justify-center lg:px-2' : ''} ${isActive ? 'bg-[var(--complementary-soft)] text-[var(--text-main)]' : 'text-[var(--text-muted)] hover:bg-[var(--bg-surface-muted)] hover:text-[var(--text-main)]'}`}
            >
              {({ isActive }) => (
                <>
                  <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${isActive ? 'bg-[#684cf2] text-white' : 'bg-[var(--bg-surface-muted)] text-[var(--brand)]'}`}><Icon size={18} /></span>
                  <span className={`min-w-0 flex-1 font-semibold ${collapsed ? 'lg:hidden' : ''}`}>{label}</span>
                  <ChevronRight size={15} className={`shrink-0 opacity-40 transition group-hover:translate-x-0.5 ${collapsed ? 'lg:hidden' : ''}`} />
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mb-3 flex items-center justify-between border-t border-[var(--border-soft)] pt-4 lg:hidden">
          <span className="text-xs font-semibold text-[var(--text-muted)]">Aparência</span><ThemeToggle />
        </div>
        <div className="mt-4 border-t border-[var(--border-soft)] pt-4">
          <div className={`flex items-center gap-3 ${collapsed ? 'lg:flex-col lg:gap-2' : ''}`}>
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#684cf2,#df50f2)] text-sm font-bold text-white">{user?.name?.charAt(0).toUpperCase() ?? 'O'}</span>
            <div className={`min-w-0 flex-1 ${collapsed ? 'lg:hidden' : ''}`}><p className="truncate text-sm font-semibold">{user?.name ?? 'Conta'}</p><p className="truncate text-xs text-[var(--text-muted)]">{user?.email}</p></div>
            <button type="button" onClick={() => { void logout(); }} className="rounded-lg p-2 text-[var(--danger-text)] hover:bg-[var(--danger-soft)]" aria-label="Sair da conta" title="Sair"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>

      {open && <button type="button" className="fixed inset-0 z-30 bg-black/55 backdrop-blur-sm lg:hidden" onClick={() => setOpen(false)} aria-label="Fechar menu" />}

      <main className={`min-w-0 transition-[margin] duration-200 ${collapsed ? 'lg:ml-[5.25rem]' : 'lg:ml-[18rem]'}`}>
        <header className="sticky top-0 z-20 border-b border-[var(--border-soft)] bg-[color-mix(in_srgb,var(--bg-app)_84%,transparent)] px-5 py-3 backdrop-blur-xl sm:px-8">
          <div className="mx-auto flex max-w-[1280px] items-center gap-3">
            <button type="button" className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] lg:hidden" onClick={() => setOpen(true)} aria-label="Abrir menu"><Menu size={19} /></button>
            <div className="hidden min-w-0 flex-1 xl:block"><p className="eyebrow">Operum</p><p className="mt-1 truncate text-sm text-[var(--text-muted)]">Controle claro, análise quando você precisar.</p></div>
            <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-3 xl:flex-none">
              <div className="min-w-0 flex-1 sm:w-[18rem] sm:flex-none">
                <label htmlFor="active-portfolio" className="mb-1 hidden font-data text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)] sm:block">Carteira ativa</label>
                <Select id="active-portfolio" value={activePortfolioId} onChange={(event) => setActivePortfolioId(event.target.value)} disabled={!portfolios.length} className="!min-h-10 !rounded-lg !border !border-[var(--border-soft)] !bg-[var(--bg-surface)] !px-3 !py-2 focus:!px-3">
                  {!portfolios.length && <option value="">Nenhuma carteira</option>}
                  {!!portfolios.length && <option value={ALL_PORTFOLIOS_ID}>Todas as carteiras</option>}
                  {portfolios.map((portfolio) => <option key={portfolio.id} value={portfolio.id}>{getPortfolioLabel(portfolio)}</option>)}
                </Select>
              </div>
              <ThemeToggle className="hidden sm:inline-flex" />
            </div>
          </div>
        </header>
        <div className="app-page mx-auto max-w-[1280px] p-5 sm:p-8"><Outlet /></div>
      </main>
    </div>
  );
}
