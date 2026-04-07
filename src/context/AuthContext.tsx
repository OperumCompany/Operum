import { createContext, useContext, useMemo, useState } from 'react';
import { defaultUser } from '../data/mocks';
import { User } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';

type AuthContextType = {
  user: User | null;
  login: (email: string, password: string) => { ok: boolean; message: string };
  register: (userData: User) => { ok: boolean; message: string };
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [storedUser, setStoredUser] = useState<User>(() => readStorage(storageKeys.user, defaultUser));
  const [session, setSession] = useState<User | null>(() => readStorage<User | null>(storageKeys.session, null));

  const value = useMemo<AuthContextType>(() => ({
    user: session,
    login: (email, password) => {
      if (email === storedUser.email && password === storedUser.password) {
        setSession(storedUser);
        writeStorage(storageKeys.session, storedUser);
        return { ok: true, message: 'Login realizado com sucesso.' };
      }
      return { ok: false, message: 'Credenciais inválidas. Use o usuário mockado.' };
    },
    register: (userData) => {
      setStoredUser(userData);
      writeStorage(storageKeys.user, userData);
      setSession(userData);
      writeStorage(storageKeys.session, userData);
      return { ok: true, message: 'Conta criada com sucesso.' };
    },
    logout: () => {
      setSession(null);
      writeStorage(storageKeys.session, null);
    },
  }), [session, storedUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
