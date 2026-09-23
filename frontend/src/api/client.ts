import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";
import type { AuthTokens } from "../types";

// Relative "/api" works both with the Vite dev proxy and the nginx container.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

const ACCESS_KEY = "bookai.access";
const REFRESH_KEY = "bookai.refresh";

export const tokenStorage = {
  get(): AuthTokens | null {
    try {
      const access = localStorage.getItem(ACCESS_KEY);
      const refresh = localStorage.getItem(REFRESH_KEY);
      return access && refresh ? { access, refresh } : null;
    } catch {
      return null;
    }
  },
  set(tokens: AuthTokens) {
    try {
      localStorage.setItem(ACCESS_KEY, tokens.access);
      localStorage.setItem(REFRESH_KEY, tokens.refresh);
    } catch {
      /* storage unavailable (private mode) — session simply won't persist */
    }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
};

type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const tokens = tokenStorage.get();
  if (tokens?.access && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${tokens.access}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const tokens = tokenStorage.get();
  if (!tokens?.refresh) return null;
  if (!refreshPromise) {
    refreshPromise = axios
      .post<{ access: string; refresh?: string }>(`${API_BASE_URL}/auth/token/refresh/`, { refresh: tokens.refresh })
      .then((res) => {
        const next: AuthTokens = { access: res.data.access, refresh: res.data.refresh ?? tokens.refresh };
        tokenStorage.set(next);
        return next.access;
      })
      .catch(() => {
        tokenStorage.clear();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;
    const isAuthRoute = original?.url?.includes("/auth/login") || original?.url?.includes("/auth/token/refresh");

    if (status === 401 && original && !original._retried && !isAuthRoute) {
      original._retried = true;
      const access = await refreshAccessToken();
      if (access) {
        original.headers = { ...(original.headers ?? {}), Authorization: `Bearer ${access}` };
        return api.request(original);
      }
      unauthorizedListeners.forEach((listener) => listener());
    }
    return Promise.reject(error);
  },
);

/** Turn any API error into a human-readable message (never a stack trace). */
export function getErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (!error.response) return "Cannot reach the server. Is the backend running?";
    if (data) {
      if (typeof data.detail === "string") return data.detail;
      const firstKey = Object.keys(data)[0];
      const value = firstKey ? data[firstKey] : undefined;
      if (Array.isArray(value) && typeof value[0] === "string") {
        return firstKey === "non_field_errors" ? value[0] : `${firstKey}: ${value[0]}`;
      }
      if (typeof value === "string") return `${firstKey}: ${value}`;
    }
    return `${fallback} (HTTP ${error.response.status})`;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}
