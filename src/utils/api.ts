const API_BASE = '/api';
const AUTH_TOKEN_KEY = 'operum_auth_token';

type ApiRequestOptions = RequestInit & {
  auth?: boolean;
};

class ApiClient {
  private async request<T>(path: string, options?: ApiRequestOptions): Promise<T> {
    const url = `${API_BASE}${path}`;
    const { auth = true, headers, ...fetchOptions } = options ?? {};
    let token: string | null = null;
    if (auth) {
      try {
        token = JSON.parse(localStorage.getItem(AUTH_TOKEN_KEY) ?? 'null');
      } catch {
        token = null;
      }
    }
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
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown, options?: ApiRequestOptions): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  postPublic<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      auth: false,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  del<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'DELETE',
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

const api = new ApiClient();
export default api;
