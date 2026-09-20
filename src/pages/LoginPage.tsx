import { FormEvent, useState } from 'react';
import { LoaderCircle, ShieldCheck, TrendingUp } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input } from '../components/UI';
import { Brand } from '../components/Brand';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const res = await login(email, password);
      setMessage({
        ok: res.ok,
        text: res.ok ? res.message : 'Nao foi possivel entrar. Verifique seu e-mail e senha e tente novamente.',
      });
      if (res.ok) navigate('/app');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-[var(--bg-app)] px-5 py-5 sm:px-8 sm:py-8">
      <div className="mx-auto mb-5 flex max-w-6xl items-center justify-between"><Brand /><ThemeToggle /></div>
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative overflow-hidden rounded-3xl bg-[#0d0d0d] p-7 text-white shadow-[var(--shadow-card)] sm:p-10">
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-[var(--ai-gradient)] opacity-30 blur-3xl" />
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold">
              <TrendingUp size={16} />
              Previsao de ativos com contexto
            </div>
            <h1 className="mt-6 text-4xl font-bold leading-tight">
              Entre para acompanhar previsoes, noticias e cenarios da sua carteira.
            </h1>
            <p className="mt-4 text-base leading-7 text-white/75">
              O Operum conecta noticias, status dos ativos e IA para transformar dados em analises claras. Crie carteiras diferentes, simule estrategias e acompanhe sinais sem perder o contexto.
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            <div className="rounded-[28px] bg-white/8 p-5">
              <p className="text-sm font-semibold">Previsoes por ativo</p>
              <p className="mt-2 text-sm leading-6 text-white/72">
                Veja horizontes, sinais recentes e fatores que podem mudar a leitura dos seus ativos.
              </p>
            </div>
            <div className="rounded-[28px] bg-white/8 p-5">
              <p className="text-sm font-semibold">Carteiras para simular</p>
              <p className="mt-2 text-sm leading-6 text-white/72">
                Separe estrategias, compare cenarios e entenda onde cada tese fica mais exposta.
              </p>
            </div>
          </div>
        </section>

        <section className="flex items-center">
          <form onSubmit={handleSubmit} className="surface-card w-full rounded-3xl p-7 sm:p-10">
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-4 py-2 text-sm font-semibold text-[var(--text-main)]">
              <ShieldCheck size={16} />
              Acesso seguro
            </div>
            <h2 className="mt-6 text-3xl font-bold text-[var(--text-main)]">Entrar no Operum</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Entre para ver suas carteiras, previsoes com IA, noticias relacionadas e analises prontas para comparar.
            </p>

            <div className="mt-8 space-y-4">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Seu e-mail" required />
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Sua senha" required />
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? <><LoaderCircle size={16} className="animate-spin" />Entrando...</> : 'Entrar'}
              </Button>
            </div>

            {message && (
              <p className={`mt-4 text-sm ${message.ok ? 'text-[var(--success-text)]' : 'text-[var(--danger-text)]'}`}>
                {message.text}
              </p>
            )}

            <div className="mt-6 rounded-[24px] bg-[var(--bg-surface-strong)] p-4 text-sm leading-6 text-[var(--text-muted)]">
              Novo por aqui? Entre, abra <strong className="text-[var(--text-main)]">Carteiras</strong> e use um exemplo pronto para testar previsoes e simulacoes.
            </div>
            <p className="mt-6 text-sm text-[var(--text-muted)]">
              Ainda nao possui conta?{' '}
              <Link to="/registro" className="font-semibold text-[var(--brand)]">
                Criar conta
              </Link>
            </p>
            <Link to="/" className="mt-4 inline-block text-sm font-semibold text-[var(--text-muted)] hover:text-[var(--text-main)]">Voltar para o inicio</Link>
          </form>
        </section>
      </div>
    </div>
  );
}
