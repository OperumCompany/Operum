export function resolveApiBaseUrl(configuredUrl?: string): string {
  const normalized = configuredUrl?.trim().replace(/\/+$/, '');
  return normalized || '/api';
}

const viteEnv = (import.meta as ImportMeta & { env?: { VITE_API_BASE_URL?: string } }).env;
const API_BASE = resolveApiBaseUrl(viteEnv?.VITE_API_BASE_URL);

type ApiRequestOptions = RequestInit & {
  auth?: boolean;
  skipRefresh?: boolean;
};

class ApiClient {
  private readonly inFlightGets = new Map<string, Promise<unknown>>();
  private refreshRequest: Promise<unknown> | null = null;

  private invalidateInFlightGets(): void {
    this.inFlightGets.clear();
  }

  private shouldTryRefresh(path: string, options?: ApiRequestOptions): boolean {
    if (options?.auth === false || options?.skipRefresh) return false;
    return !['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'].includes(path);
  }

  private async refreshSession(): Promise<void> {
    if (!this.refreshRequest) {
      this.refreshRequest = this.request('/auth/refresh', {
        method: 'POST',
        skipRefresh: true,
      }).finally(() => {
        this.refreshRequest = null;
      });
    }
    await this.refreshRequest;
  }

  private async request<T>(path: string, options?: ApiRequestOptions): Promise<T> {
    const url = `${API_BASE}${path}`;
    const { auth: _auth = true, skipRefresh: _skipRefresh = false, headers, ...fetchOptions } = options ?? {};
    const res = await fetch(url, {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      ...fetchOptions,
    });
    if (res.status === 401 && this.shouldTryRefresh(path, options)) {
      await this.refreshSession();
      return this.request<T>(path, { ...options, skipRefresh: true });
    }
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body || res.statusText}`);
    }
    return res.json();
  }

  get<T>(path: string): Promise<T> {
    const key = path;
    const existing = this.inFlightGets.get(key) as Promise<T> | undefined;
    if (existing) return existing;

    const request = this.request<T>(path);
    this.inFlightGets.set(key, request);
    const clear = () => {
      if (this.inFlightGets.get(key) === request) this.inFlightGets.delete(key);
    };
    request.then(clear, clear);
    return request;
  }

  post<T>(path: string, body?: unknown, options?: ApiRequestOptions): Promise<T> {
    this.invalidateInFlightGets();
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  postPublic<T>(path: string, body?: unknown): Promise<T> {
    this.invalidateInFlightGets();
    return this.request<T>(path, {
      method: 'POST',
      auth: false,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    this.invalidateInFlightGets();
    return this.request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    this.invalidateInFlightGets();
    return this.request<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  del<T>(path: string, body?: unknown): Promise<T> {
    this.invalidateInFlightGets();
    return this.request<T>(path, {
      method: 'DELETE',
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

const api = new ApiClient();
export default api;
