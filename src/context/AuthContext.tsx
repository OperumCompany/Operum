import { createContext, useContext, useMemo, useState } from 'react';
import { defaultUser } from '../data/mocks';
import { User } from '../types';
import { readStorage, storageKeys, writeStorage } from '../utils/storage';

type AuthContextType = {
  user: User | null;
  users: User[];
  login: (email: string, password: string) => { ok: boolean; message: string };
  register: (userData: User) => { ok: boolean; message: string };
  updatePassword: (nextPassword: string) => { ok: boolean; message: string };
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function normalizeUsers(users: User[]) {
  const byEmail = new Map<string, User>();

  [...users, defaultUser].forEach((candidate) => {
    byEmail.set(candidate.email.trim().toLowerCase(), {
      ...candidate,
      name: candidate.name.trim(),
      email: candidate.email.trim().toLowerCase(),
    });
  });

  return Array.from(byEmail.values());
}

function getInitialUsers() {
  const storedUsers = readStorage<User[]>(storageKeys.users, []);
  const legacyUser = readStorage<User | null>(storageKeys.user, null);
  return normalizeUsers(legacyUser ? [...storedUsers, legacyUser] : storedUsers);
}

function getInitialSession(users: User[]) {
  const storedSession = readStorage<User | null>(storageKeys.session, null);
  if (!storedSession) return null;

  return users.find((candidate) => candidate.email === storedSession.email.trim().toLowerCase()) ?? null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<User[]>(() => getInitialUsers());
  const [session, setSession] = useState<User | null>(() => getInitialSession(getInitialUsers()));

  const value = useMemo<AuthContextType>(() => ({
    user: session,
    users,
    login: (email, password) => {
      const normalizedEmail = email.trim().toLowerCase();
      const matchedUser = users.find((candidate) => candidate.email === normalizedEmail);

      if (matchedUser && password === matchedUser.password) {
        setSession(matchedUser);
        writeStorage(storageKeys.session, matchedUser);
        return { ok: true, message: 'Login realizado com sucesso.' };
      }

      return { ok: false, message: 'Credenciais inválidas. Você também pode usar a conta de exemplo da Camila.' };
    },
    register: (userData) => {
      const normalizedUser = {
        ...userData,
        name: userData.name.trim(),
        email: userData.email.trim().toLowerCase(),
      };

      if (users.some((candidate) => candidate.email === normalizedUser.email)) {
        return { ok: false, message: 'Já existe uma conta cadastrada com este e-mail.' };
      }

      const nextUsers = normalizeUsers([...users, normalizedUser]);
      setUsers(nextUsers);
      writeStorage(storageKeys.users, nextUsers);
      setSession(normalizedUser);
      writeStorage(storageKeys.session, normalizedUser);
      return { ok: true, message: 'Conta criada com sucesso.' };
    },
    updatePassword: (nextPassword) => {
      if (!session) {
        return { ok: false, message: 'Nenhuma sessão ativa.' };
      }

      if (session.email === defaultUser.email) {
        return { ok: false, message: 'A conta da Camila é fixa para demonstração e não pode ter a senha alterada.' };
      }

      const normalizedPassword = nextPassword.trim();
      const nextUsers = users.map((candidate) =>
        candidate.id === session.id ? { ...candidate, password: normalizedPassword } : candidate,
      );
      const nextSession = nextUsers.find((candidate) => candidate.id === session.id) ?? session;

      setUsers(nextUsers);
      writeStorage(storageKeys.users, nextUsers);
      setSession(nextSession);
      writeStorage(storageKeys.session, nextSession);
      return { ok: true, message: 'Senha alterada com sucesso.' };
    },
    logout: () => {
      setSession(null);
      writeStorage(storageKeys.session, null);
    },
  }), [session, users]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
