import { FormEvent, useEffect, useState } from 'react';
import { LogOut, Palette, ShieldCheck, Trash2, UserRound, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Input, StatusMessage } from '../components/UI';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

type Feedback = { message: string; tone: 'success' | 'error' } | null;

export function SettingsPage() {
  const { user, logout, updatePassword, deleteAccount } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deletionPassword, setDeletionPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!isDeleteOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleting) closeDeletionDialog();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isDeleteOpen, deleting]);

  function closeDeletionDialog() {
    setIsDeleteOpen(false);
    setDeletionPassword('');
    setConfirmation('');
  }

  async function handlePasswordUpdate(event: FormEvent) {
    event.preventDefault();
    if (password.length < 6) {
      setFeedback({ message: 'A nova senha precisa ter pelo menos 6 caracteres.', tone: 'error' });
      return;
    }

    const result = await updatePassword(currentPassword, password);
    setFeedback({ message: result.message, tone: result.ok ? 'success' : 'error' });
    if (result.ok) {
      setCurrentPassword('');
      setPassword('');
    }
  }

  async function handleAccountDeletion(event: FormEvent) {
    event.preventDefault();
    if (confirmation !== 'Excluir' || !deletionPassword) return;

    setDeleting(true);
    const result = await deleteAccount(deletionPassword, confirmation);
    setDeleting(false);
    if (result.ok) {
      closeDeletionDialog();
      navigate('/login', { replace: true });
      return;
    }
    setFeedback({ message: result.message, tone: 'error' });
  }

  return (
    <div className="space-y-5">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,var(--bg-surface-strong)_60%,rgba(61,77,156,0.08)_100%)] p-5 shadow-[var(--shadow-card)] sm:p-7">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Configurações</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-main)] sm:text-4xl">Sua conta, do seu jeito</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-muted)]">Consulte seus dados, mantenha a conta protegida e escolha a aparência do Operum.</p>
      </section>

      {feedback && <StatusMessage tone={feedback.tone}>{feedback.message}</StatusMessage>}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Seus dados" right={<UserRound size={17} className="text-[var(--brand)]" />}>
          <dl className="space-y-4">
            <div className="rounded-2xl bg-[var(--bg-surface-muted)] px-4 py-3"><dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Nome</dt><dd className="mt-1 text-sm font-semibold text-[var(--text-main)]">{user?.name}</dd></div>
            <div className="rounded-2xl bg-[var(--bg-surface-muted)] px-4 py-3"><dt className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">E-mail</dt><dd className="mt-1 break-all text-sm font-semibold text-[var(--text-main)]">{user?.email}</dd></div>
          </dl>
        </Card>

        <Card title="Aparência" right={<Palette size={17} className="text-[var(--brand)]" />}>
          <div className="flex flex-col gap-4 rounded-2xl bg-[var(--bg-surface-muted)] p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-[var(--text-main)]">Tema {theme === 'dark' ? 'escuro' : 'claro'}</p>
              <p className="mt-1 text-sm leading-6 text-[var(--text-muted)]">A escolha fica salva somente neste dispositivo.</p>
            </div>
            <ThemeToggle />
          </div>
        </Card>

        <Card title="Segurança" right={<ShieldCheck size={17} className="text-[var(--brand)]" />} className="xl:col-span-2">
          <form onSubmit={handlePasswordUpdate} className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
            <label className="block text-sm font-medium text-[var(--text-main)]">Senha atual<Input className="mt-1" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="Digite sua senha atual" required autoComplete="current-password" /></label>
            <label className="block text-sm font-medium text-[var(--text-main)]">Nova senha<Input className="mt-1" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Mínimo de 6 caracteres" required minLength={6} autoComplete="new-password" /></label>
            <div className="flex flex-wrap gap-2"><Button type="submit">Alterar senha</Button><Button type="button" variant="ghost" onClick={() => { void logout(); }}><LogOut size={16} /> Sair</Button></div>
          </form>
        </Card>
      </div>

      <section className="rounded-2xl border border-[var(--danger-text)]/30 bg-[var(--danger-soft)] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="text-lg font-semibold text-[var(--danger-text)]">Zona de perigo</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--text-main)]">A exclusão remove permanentemente sua conta, sessões, carteiras, movimentações e conversas. Esta ação não pode ser desfeita.</p></div>
          <Button type="button" variant="danger" className="shrink-0" onClick={() => setIsDeleteOpen(true)}><Trash2 size={16} /> Excluir conta</Button>
        </div>
      </section>

      {isDeleteOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation" onMouseDown={() => { if (!deleting) closeDeletionDialog(); }}>
        <div className="w-full max-w-md rounded-[28px] border border-[var(--border-soft)] bg-[var(--bg-surface-strong)] p-6 shadow-2xl sm:p-7" role="dialog" aria-modal="true" aria-labelledby="delete-account-title" onMouseDown={(event) => event.stopPropagation()}>
          <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-[var(--danger-text)]">Ação irreversível</p><h2 id="delete-account-title" className="mt-1 text-2xl font-bold text-[var(--text-main)]">Excluir conta?</h2></div><button type="button" onClick={closeDeletionDialog} disabled={deleting} className="rounded-full p-2 text-[var(--text-muted)] hover:bg-[var(--bg-surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] disabled:opacity-50" aria-label="Fechar confirmação"><X size={20} /></button></div>
          <p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">Para confirmar, informe sua senha atual e digite <strong className="text-[var(--text-main)]">Excluir</strong> no campo abaixo.</p>
          <form className="mt-5 space-y-4" onSubmit={handleAccountDeletion}>
            <label className="block text-sm font-medium text-[var(--text-main)]">Senha atual<Input className="mt-1" type="password" value={deletionPassword} onChange={(event) => setDeletionPassword(event.target.value)} autoComplete="current-password" required autoFocus /></label>
            <label className="block text-sm font-medium text-[var(--text-main)]">Digite “Excluir”<Input className="mt-1" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="Excluir" required /></label>
            <div className="flex flex-wrap justify-end gap-3 pt-2"><Button type="button" variant="ghost" onClick={closeDeletionDialog} disabled={deleting}>Cancelar</Button><Button type="submit" variant="danger" disabled={deleting || !deletionPassword || confirmation !== 'Excluir'}>{deleting ? 'Excluindo conta...' : 'Confirmar exclusão'}</Button></div>
          </form>
        </div>
      </div>}
    </div>
  );
}
