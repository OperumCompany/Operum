import { FormEvent, useEffect, useState } from 'react';
import { Bell, SlidersHorizontal, UserRound } from 'lucide-react';
import { Button, Card, Input } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { NewsCategory, UserPreferences } from '../types';
import api from '../utils/api';

const topics: NewsCategory[] = ['Inflação', 'Juros', 'Tecnologia', 'Criptomoedas', 'Ações', 'Exterior', 'Política econômica', 'Renda fixa'];
const defaultPreferences: UserPreferences = {
  topics: ['Inflação', 'Juros', 'Ações', 'Exterior'],
  compactMode: false,
  notifications: true,
};

export function SettingsPage() {
  const { user, logout, updatePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState('');
  const [prefs, setPrefs] = useState<UserPreferences>(defaultPreferences);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<UserPreferences>('/auth/preferences')
      .then((data) => setPrefs({
        topics: (data.topics?.length ? data.topics : defaultPreferences.topics) as NewsCategory[],
        compactMode: !!data.compactMode,
        notifications: !!data.notifications,
      }))
      .catch(() => setPrefs(defaultPreferences))
      .finally(() => setLoading(false));
  }, []);

  async function savePrefs() {
    try {
      const saved = await api.put<UserPreferences>('/auth/preferences', prefs);
      setPrefs(saved);
      setFeedback('Preferências salvas com sucesso.');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Falha ao salvar preferências.');
    }
  }

  async function handlePasswordUpdate(e: FormEvent) {
    e.preventDefault();
    if (password.length < 6) {
      setFeedback('A senha precisa ter pelo menos 6 caracteres.');
      return;
    }

    const result = await updatePassword(currentPassword, password);
    setFeedback(result.message);
    if (result.ok) {
      setCurrentPassword('');
      setPassword('');
    }
  }

  return (
    <div className="space-y-4">
      <section className="rounded-[30px] border border-[var(--border-soft)] bg-[linear-gradient(120deg,rgba(225,94,242,0.08)_0%,rgba(255,255,255,0.96)_60%,rgba(61,77,156,0.08)_100%)] p-6 shadow-[var(--shadow-card)]">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">Configurações</p>
        <h2 className="mt-2 text-3xl font-bold">Ajuste sua experiência no Operum</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">
          Escolha os temas que quer acompanhar, configure alertas e mantenha sua conta atualizada.
        </p>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Seus dados" right={<UserRound size={16} className="text-[var(--brand)]" />}>
          <p className="text-sm"><strong>Nome:</strong> {user?.name}</p>
          <p className="mt-2 text-sm"><strong>E-mail:</strong> {user?.email}</p>
        </Card>

        <Card title="Segurança">
          <form onSubmit={handlePasswordUpdate} className="space-y-3">
            <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="Senha atual" />
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Nova senha" />
            <div className="flex flex-wrap gap-2">
              <Button type="submit">Alterar senha</Button>
              <button type="button" className="rounded-2xl border border-[var(--border-soft)] px-4 py-2.5 text-sm font-semibold text-[var(--danger-text)]" onClick={() => { void logout(); }}>
                Sair da conta
              </button>
            </div>
          </form>
        </Card>

        <Card title="Temas de notícias" right={<Bell size={16} className="text-[var(--brand)]" />}>
          {loading ? (
            <p className="text-sm text-[var(--text-muted)]">Carregando preferências...</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {topics.map((t) => (
                <label key={t} className="rounded-[18px] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm">
                  <input
                    type="checkbox"
                    checked={prefs.topics.includes(t)}
                    onChange={(e) =>
                      setPrefs((prev) => ({
                        ...prev,
                        topics: e.target.checked ? [...prev.topics, t] : prev.topics.filter((x) => x !== t),
                      }))
                    }
                  />{' '}
                  <span className="ml-1">{t}</span>
                </label>
              ))}
            </div>
          )}
        </Card>

        <Card title="Preferências da interface" right={<SlidersHorizontal size={16} className="text-[var(--brand)]" />}>
          <label className="block rounded-[18px] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm">
            <input
              type="checkbox"
              checked={prefs.compactMode}
              onChange={(e) => setPrefs((prev) => ({ ...prev, compactMode: e.target.checked }))}
            />{' '}
            <span className="ml-1">Modo compacto</span>
          </label>
          <label className="mt-3 block rounded-[18px] bg-[var(--bg-surface-strong)] px-4 py-3 text-sm">
            <input
              type="checkbox"
              checked={prefs.notifications}
              onChange={(e) => setPrefs((prev) => ({ ...prev, notifications: e.target.checked }))}
            />{' '}
            <span className="ml-1">Alertas locais</span>
          </label>
          <Button className="mt-4" onClick={savePrefs}>Salvar preferências</Button>
        </Card>
      </div>

      {feedback && <p className="text-sm font-semibold text-[var(--brand)]">{feedback}</p>}
    </div>
  );
}
