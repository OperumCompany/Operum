import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-[var(--text-muted)]">Carregando sessao...</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
