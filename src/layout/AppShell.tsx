import { Menu, LayoutDashboard, Newspaper, MessageCircle, BriefcaseBusiness, Settings, LogOut } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/noticias', label: 'Noticias', icon: Newspaper },
  { to: '/chat', label: 'Chat', icon: MessageCircle },
  { to: '/carteiras', label: 'Carteiras', icon: BriefcaseBusiness },
  { to: '/configuracoes', label: 'Configuracoes', icon: Settings },
];

export function AppShell() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[#F2F2F2] text-[#252525]">
      <div className="flex w-full">
        <aside className={`fixed left-0 top-0 z-30 h-screen w-72 bg-[#252525] p-5 text-white transition ${open ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
          <h1 className="mb-8 text-2xl font-bold">Operum</h1>
          <nav className="space-y-2">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setOpen(false)}
                className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${isActive ? 'bg-[#3D4D9C]' : 'hover:bg-white/10'}`}
              >
                <Icon size={18} /> {label}
              </NavLink>
            ))}
          </nav>
          <button onClick={logout} className="mt-8 flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-[#E15EF2] hover:bg-white/10">
            <LogOut size={18} /> Sair
          </button>
        </aside>

        {open && <button className="fixed inset-0 z-20 bg-black/30 md:hidden" onClick={() => setOpen(false)} />}

        <main className="min-w-0 flex-1 md:ml-72">
          <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[#A5A5A5]/30 bg-[#F2F2F2]/95 px-4 py-3 backdrop-blur sm:px-6">
            <button className="rounded-lg bg-white p-2 md:hidden" onClick={() => setOpen(true)}><Menu size={18} /></button>
            <div className="text-right">
              <p className="text-xs text-[#717171]">Bem-vinda</p>
              <p className="text-sm font-semibold">{user?.name}</p>
            </div>
          </header>
          <div className="p-4 sm:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}