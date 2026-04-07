import { FormEvent, useState } from 'react';
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
    <div className="flex min-h-screen items-center justify-center bg-[#F2F2F2] px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-3xl bg-white p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-[#252525]">Operum</h1>
        <p className="mt-2 text-sm text-[#717171]">Apoio inteligente para decisões financeiras.</p>
        <div className="mt-6 space-y-3">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-mail" required />
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Senha" required />
          <Button type="submit" className="w-full">Entrar</Button>
        </div>
        {message && <p className={`mt-3 text-sm ${message.ok ? 'text-green-600' : 'text-[#C7559B]'}`}>{message.text}</p>}
        <p className="mt-5 text-sm text-[#717171]">Não possui conta? <Link to="/registro" className="font-semibold text-[#3D4D9C]">Registrar</Link></p>
      </form>
    </div>
  );
}
