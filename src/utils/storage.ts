export const storageKeys = {
  user: 'operum_user',
  users: 'operum_users',
  session: 'operum_session',
  portfolios: 'operum_portfolios',
  activePortfolio: 'operum_active_portfolio',
  chat: 'operum_chat',
  preferences: 'operum_preferences',
};

export function readStorage<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeStorage<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getScopedStorageKey(key: string, scope?: string | null): string {
  return scope ? `${key}:${scope}` : key;
}
