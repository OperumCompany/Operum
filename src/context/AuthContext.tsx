import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../utils/api';
import { AuthResponse, User } from '../types';

type AuthContextType = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ ok: boolean; message: string }>;
  register: (userData: { name: string; email: string; password: string }) => Promise<{ ok: boolean; message: string }>;
  updatePassword: (currentPassword: string, nextPassword: string) => Promise<{ ok: boolean; message: string }>;
  deleteAccount: (currentPassword: string, confirmation: string) => Promise<{ ok: boolean; message: string }>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<User>('/auth/me')
      .then(setUser)
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextType>(() => ({
    user,
    loading,
    login: async (email, password) => {
      try {
        const response = await api.postPublic<AuthResponse>('/auth/login', { email, password });
        setUser(response.user);
        return { ok: true, message: 'Login realizado com sucesso.' };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Falha no login.';
        return { ok: false, message };
      }
    },
    register: async (userData) => {
      try {
        const response = await api.postPublic<AuthResponse>('/auth/register', userData);
        setUser(response.user);
        return { ok: true, message: 'Conta criada com sucesso.' };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Falha no cadastro.';
        return { ok: false, message };
      }
    },
    updatePassword: async (currentPassword, nextPassword) => {
      try {
        const updatedUser = await api.put<User>('/auth/password', {
          current_password: currentPassword,
          new_password: nextPassword,
        });
        setUser(updatedUser);
        return { ok: true, message: 'Senha alterada com sucesso.' };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Falha ao alterar senha.';
        return { ok: false, message };
      }
    },
    deleteAccount: async (currentPassword, confirmation) => {
      try {
        await api.del<{ status: string }>('/auth/account', {
          current_password: currentPassword,
          confirmation,
        });
        setUser(null);
        return { ok: true, message: 'Conta excluida com sucesso.' };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Falha ao excluir a conta.';
        return { ok: false, message };
      }
    },
    logout: async () => {
      setUser(null);
      try {
        await api.post('/auth/logout');
      } catch {
        // noop
      }
    },
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
