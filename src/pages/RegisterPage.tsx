import { FormEvent, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input } from '../components/UI';
import { useAuth } from '../context/AuthContext';

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (!accept) return setError('Voce precisa aceitar os termos para continuar.');
    if (password.length < 6) return setError('A senha deve ter ao menos 6 caracteres.');
    if (password !== confirmPassword) return setError('As senhas nao coincidem.');

    const result = register({ id: crypto.randomUUID(), name, email, password });
    if (!result.ok) {
      setError(result.message);
      return;
    }

    navigate('/');
  }

  return (
    <div className="min-h-screen bg-[var(--bg-app)] px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-5xl gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-[36px] border border-[var(--border-soft)] bg-[linear-gradient(135deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_60%,rgba(61,77,156,0.1)_100%)] p-8 shadow-[var(--shadow-card)] sm:p-10">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Criar conta</p>
          <h1 className="mt-4 text-4xl font-bold leading-tight text-[var(--text-main)]">
            Monte sua base para acompanhar investimentos com mais clareza.
          </h1>
          <div className="mt-8 space-y-4">
            {[
              'Organize seus ativos em poucos passos.',
              'Receba explicacoes com menos jargao.',
              'Acesse uma visao simples e outra tecnica da carteira.',
            ].map((item) => (
              <div key={item} className="flex items-start gap-3 rounded-[24px] bg-white/80 p-4">
                <CheckCircle2 size={18} className="mt-1 text-[var(--brand)]" />
                <p className="text-sm leading-6 text-[var(--text-muted)]">{item}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="flex items-center">
          <form onSubmit={handleSubmit} className="w-full rounded-[36px] border border-[var(--border-soft)] bg-[var(--bg-surface)] p-8 shadow-[var(--shadow-card)] sm:p-10">
            <h2 className="text-3xl font-bold text-[var(--text-main)]">Criar conta no Operum</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
              Preencha seus dados para comecar pela visao amigavel da plataforma.
            </p>

            <div className="mt-8 space-y-4">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome completo" required />
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-mail" required />
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Senha" required />
              <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirmar senha" required />
            </div>

            <label className="mt-5 flex items-start gap-3 rounded-[20px] bg-[var(--bg-surface-strong)] p-4 text-sm leading-6 text-[var(--text-muted)]">
              <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-1" />
              <span>Aceito os termos para criar minha conta e usar a plataforma.</span>
            </label>

            <Button type="submit" className="mt-6 w-full">Criar conta</Button>
            {error && <p className="mt-4 text-sm text-[var(--danger-text)]">{error}</p>}

            <p className="mt-6 text-sm text-[var(--text-muted)]">
              Ja tem conta?{' '}
              <Link to="/login" className="font-semibold text-[var(--brand)]">
                Entrar
              </Link>
            </p>
          </form>
        </section>
      </div>
    </div>
  );
}
