import { FormEvent, useState } from 'react';
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
    if (!accept) return setError('Você precisa aceitar os termos.');
    if (password.length < 6) return setError('A senha deve ter ao menos 6 caracteres.');
    if (password !== confirmPassword) return setError('As senhas não coincidem.');
    register({ id: crypto.randomUUID(), name, email, password });
    navigate('/');
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F2F2F2] px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-3xl bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Criar conta no Operum</h1>
        <div className="mt-5 space-y-3">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome completo" required />
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-mail" required />
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Senha" required />
          <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirmar senha" required />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} /> Aceito os termos.</label>
          <Button type="submit" className="w-full">Criar conta</Button>
        </div>
        {error && <p className="mt-2 text-sm text-[#C7559B]">{error}</p>}
        <p className="mt-4 text-sm">Já tem conta? <Link to="/login" className="font-semibold text-[#3D4D9C]">Entrar</Link></p>
      </form>
    </div>
  );
}
