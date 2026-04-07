import { FormEvent, useState } from 'react';
import { Button, Card, Input } from '../components/UI';
import { preferencesDefault } from '../data/mocks';
import { NewsCategory } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';
import { useAuth } from '../context/AuthContext';

const topics: NewsCategory[] = ['Inflação', 'Juros', 'Tecnologia', 'Criptomoedas', 'Ações', 'Exterior', 'Política econômica', 'Renda fixa'];

export function SettingsPage() {
  const { user, logout } = useAuth();
  const [password, setPassword] = useState('');
  const [feedback, setFeedback] = useState('');
  const [prefs, setPrefs] = useState(() => readStorage(storageKeys.preferences, preferencesDefault));

  function savePrefs() {
    writeStorage(storageKeys.preferences, prefs);
    setFeedback('Preferências salvas com sucesso.');
  }

  function updatePassword(e: FormEvent) {
    e.preventDefault();
    if (password.length < 6) return setFeedback('Senha muito curta.');
    setFeedback('Senha alterada (simulação).');
    setPassword('');
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card title="Dados do usuário">
        <p className="text-sm"><strong>Nome:</strong> {user?.name}</p>
        <p className="text-sm"><strong>E-mail:</strong> {user?.email}</p>
      </Card>
      <Card title="Segurança">
        <form onSubmit={updatePassword} className="space-y-3">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Nova senha" />
          <Button type="submit">Alterar senha</Button>
          <Button type="button" className="ml-2 bg-[#C7559B]" onClick={logout}>Logout</Button>
        </form>
      </Card>
      <Card title="Preferências de notícias">
        <div className="grid gap-2 sm:grid-cols-2">{topics.map((t) => <label key={t} className="text-sm"><input type="checkbox" checked={prefs.topics.includes(t)} onChange={(e) => setPrefs((prev: typeof preferencesDefault) => ({ ...prev, topics: e.target.checked ? [...prev.topics, t] : prev.topics.filter((x) => x !== t) }))} /> <span className="ml-1">{t}</span></label>)}</div>
      </Card>
      <Card title="Preferências de interface">
        <label className="block text-sm"><input type="checkbox" checked={prefs.compactMode} onChange={(e) => setPrefs((p: typeof preferencesDefault) => ({ ...p, compactMode: e.target.checked }))} /> <span className="ml-1">Modo compacto</span></label>
        <label className="mt-2 block text-sm"><input type="checkbox" checked={prefs.notifications} onChange={(e) => setPrefs((p: typeof preferencesDefault) => ({ ...p, notifications: e.target.checked }))} /> <span className="ml-1">Alertas locais</span></label>
        <Button className="mt-3" onClick={savePrefs}>Salvar preferências</Button>
      </Card>
      {feedback && <p className="text-sm text-[#3D4D9C] xl:col-span-2">{feedback}</p>}
    </div>
  );
}
