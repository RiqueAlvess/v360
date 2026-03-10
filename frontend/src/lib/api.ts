import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { API_URL, V360_ACCESS_TOKEN_KEY, V360_REFRESH_TOKEN_KEY } from "./constants";

// Extend request config to support retry flag
interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// In-memory access token store (FE-R4: never localStorage)
let inMemoryAccessToken: string | null = null;

const SESSION_COOKIE = "session";
const REFRESH_TOKEN_KEY = "rf";

function syncSessionCookie(token: string | null): void {
  if (typeof document === "undefined") return;
  if (token) {
    document.cookie = `${SESSION_COOKIE}=${token}; path=/; SameSite=Lax`;
  } else {
    document.cookie = `${SESSION_COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
  }
}

export const tokenStore = {
  get: () => inMemoryAccessToken,
  set: (token: string | null) => {
    inMemoryAccessToken = token;
    syncSessionCookie(token);
  },
  clear: () => {
    inMemoryAccessToken = null;
    syncSessionCookie(null);
  },
};

// Refresh token stored in sessionStorage (cleared on tab/browser close)
export const refreshTokenStore = {
  get: (): string | null => {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  },
  set: (token: string | null): void => {
    if (typeof window === "undefined") return;
    if (token) {
      sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  },
  clear: (): void => {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Send httpOnly cookies for refresh token
});

// Request interceptor — attach access token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStore.get();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error)
);

// Track whether a refresh is in progress and queue pending requests
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(cb: (token: string) => void): void {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token: string): void {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

function onRefreshFailed(): void {
  refreshSubscribers = [];
}

function lsSetTokens(access: string, refresh: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(V360_ACCESS_TOKEN_KEY, access);
    localStorage.setItem(V360_REFRESH_TOKEN_KEY, refresh);
  }
}

function lsClearTokens(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(V360_ACCESS_TOKEN_KEY);
    localStorage.removeItem(V360_REFRESH_TOKEN_KEY);
  }
}

// Response interceptor — handle 401 and refresh token
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;

    if (!originalRequest) {
      return Promise.reject(error);
    }

    const isUnauthorized = error.response?.status === 401;
    const isRefreshEndpoint = originalRequest.url?.includes("/auth/refresh");
    const alreadyRetried = originalRequest._retry;

    if (isUnauthorized && !isRefreshEndpoint && !alreadyRetried) {
      if (isRefreshing) {
        // Queue the request until token is refreshed
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh((newToken: string) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            resolve(api(originalRequest));
          });
          // If refresh fails, reject
          setTimeout(() => reject(error), 10000);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const rt = refreshTokenStore.get();
        if (!rt) throw new Error("No refresh token");
        const response = await api.post<{ access_token: string; refresh_token: string }>(
          "/auth/refresh",
          { refresh_token: rt }
        );
        const newToken = response.data.access_token;
        tokenStore.set(newToken);
        refreshTokenStore.set(response.data.refresh_token);
        lsSetTokens(newToken, response.data.refresh_token);
        onTokenRefreshed(newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        tokenStore.clear();
        refreshTokenStore.clear();
        lsClearTokens();
        onRefreshFailed();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

/**
 * Generic API error type
 */
export interface ApiError {
  message: string;
  detail?: string;
  status?: number;
}

/**
 * Extract error message from Axios error
 */
export function extractApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    return {
      message:
        (data?.message as string) ||
        (data?.detail as string) ||
        error.message ||
        "Erro desconhecido",
      detail: data?.detail as string | undefined,
      status: error.response?.status,
    };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: "Erro desconhecido" };
}
