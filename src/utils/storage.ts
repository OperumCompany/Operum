export const storageKeys = {
  activePortfolio: 'operum_active_portfolio',
  chat: 'operum_chat',
  theme: 'operum_theme',
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
