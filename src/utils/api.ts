const API_BASE = '/api';
const AUTH_TOKEN_KEY = 'operum_auth_token';

type ApiRequestOptions = RequestInit & {
  auth?: boolean;
};

class ApiClient {
  private readonly inFlightGets = new Map<string, Promise<unknown>>();

  private getAuthToken(): string | null {
    try {
      return JSON.parse(localStorage.getItem(AUTH_TOKEN_KEY) ?? 'null');
    } catch {
      return null;
    }
  }

  private invalidateInFlightGets(): void {
    this.inFlightGets.clear();
  }

  private async request<T>(path: string, options?: ApiRequestOptions): Promise<T> {
    const url = `${API_BASE}${path}`;
    const { auth = true, headers, ...fetchOptions } = options ?? {};
    const token = auth ? this.getAuthToken() : null;
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      ...fetchOptions,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body || res.statusText}`);
    }
    return res.json();
  }

  get<T>(path: string): Promise<T> {
    const key = `${this.getAuthToken() ?? 'anonymous'}:${path}`;
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
