export const storageKeys = {
  user: 'operum_user',
  session: 'operum_session',
  portfolios: 'operum_portfolios',
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
