import { FormEvent, useState } from 'react';
import { Compass, ShieldCheck } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input } from '../components/UI';
import { defaultUser } from '../data/mocks';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const [email, setEmail] = useState(defaultUser.email);
  const [password, setPassword] = useState(defaultUser.password);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const res = login(email, password);
    setMessage({ ok: res.ok, text: res.message });
    if (res.ok) navigate('/');
  }

  return (
    <div className="min-h-screen bg-[var(--bg-app)] px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-[36px] bg-[#252525] p-8 text-white shadow-[var(--shadow-card)] sm:p-10">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold">
              <Compass size={16} />
              Comece pela visão mais clara da sua carteira
            </div>
            <h1 className="mt-6 text-4xl font-bold leading-tight">
              Entenda seus investimentos sem precisar falar como analista.
            </h1>
            <p className="mt-4 text-base leading-7 text-white/75">
              O Operum organiza sua carteira, explica o que está acontecendo e mostra análises mais técnicas só quando você quiser.
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            <div className="rounded-[28px] bg-white/8 p-5">
              <p className="text-sm font-semibold">Resumo amigável</p>
              <p className="mt-2 text-sm leading-6 text-white/72">
                Veja primeiro os sinais principais da sua carteira com frases simples e passos claros.
              </p>
            </div>
            <div className="rounded-[28px] bg-white/8 p-5">
              <p className="text-sm font-semibold">Painel técnico opcional</p>
              <p className="mt-2 text-sm leading-6 text-white/72">
                Para quem já conhece o mercado, os gráficos detalhados continuam a um clique de distância.
              </p>
            </div>
          </div>
        </section>

        <section className="flex items-center">
          <form onSubmit={handleSubmit} className="w-full rounded-[36px] border border-[var(--border-soft)] bg-[var(--bg-surface)] p-8 shadow-[var(--shadow-card)] sm:p-10">
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-4 py-2 text-sm font-semibold text-[var(--text-main)]">
              <ShieldCheck size={16} />
              Acesso seguro
            </div>
            <h2 className="mt-6 text-3xl font-bold text-[var(--text-main)]">Entrar no Operum</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Entre para acompanhar sua carteira, organizar ativos e receber explicações de forma simples.
            </p>

            <div className="mt-8 space-y-4">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Seu e-mail" required />
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Sua senha" required />
              <Button type="submit" className="w-full">Entrar</Button>
            </div>

            {message && (
              <p className={`mt-4 text-sm ${message.ok ? 'text-[var(--success-text)]' : 'text-[var(--danger-text)]'}`}>
                {message.text}
              </p>
            )}

            <div className="mt-6 rounded-[24px] bg-[var(--bg-surface-strong)] p-4 text-sm leading-6 text-[var(--text-muted)]">
              Não sabe por onde começar? Entre e vá para <strong className="text-[var(--text-main)]">Carteiras</strong> para usar um exemplo pronto.
            </div>
            <p className="mt-6 text-sm text-[var(--text-muted)]">
              Ainda não possui conta?{' '}
              <Link to="/registro" className="font-semibold text-[var(--brand)]">
                Criar conta
              </Link>
            </p>
          </form>
        </section>
      </div>
    </div>
  );
}
