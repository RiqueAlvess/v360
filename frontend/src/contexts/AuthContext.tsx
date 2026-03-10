"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { tokenStore, refreshTokenStore } from "@/lib/api";
import { V360_ACCESS_TOKEN_KEY, V360_REFRESH_TOKEN_KEY, ROUTES } from "@/lib/constants";
import type { UserProfile } from "@/types";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface LoginResult {
  success: true;
}

export interface LoginError {
  success: false;
  message: string;
}

export type LoginOutcome = LoginResult | LoginError;

export interface AuthContextValue {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, redirectTo?: string) => Promise<LoginOutcome>;
  logout: () => Promise<void>;
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // ── Initial session check ──────────────────────────────────────────────────
  useEffect(() => {
    const accessToken = localStorage.getItem(V360_ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(V360_REFRESH_TOKEN_KEY);

    if (!accessToken) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    // Sync into in-memory stores so axios interceptors attach the right header
    tokenStore.set(accessToken);
    if (refreshToken) refreshTokenStore.set(refreshToken);

    const initialCheck = async () => {
      try {
        const { data: profile } = await api.get<UserProfile>("/auth/me");
        if (!cancelled) {
          setUser(profile);
          setIsAuthenticated(true);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (cancelled) return;

        const status = (err as { response?: { status?: number } })?.response?.status;

        // If 401 and we still have a refresh token, attempt manual refresh.
        // (The axios interceptor may have already tried; this covers the case
        // where the interceptor itself fails, e.g. the refresh token is also
        // expired or the session was revoked server-side.)
        if (status === 401 && refreshToken) {
          try {
            const { data: refreshed } = await api.post<{
              access_token: string;
              refresh_token: string;
            }>("/auth/refresh", { refresh_token: refreshToken });

            localStorage.setItem(V360_ACCESS_TOKEN_KEY, refreshed.access_token);
            localStorage.setItem(V360_REFRESH_TOKEN_KEY, refreshed.refresh_token);
            tokenStore.set(refreshed.access_token);
            refreshTokenStore.set(refreshed.refresh_token);

            const { data: profile } = await api.get<UserProfile>("/auth/me");
            if (!cancelled) {
              setUser(profile);
              setIsAuthenticated(true);
              setIsLoading(false);
            }
          } catch {
            if (!cancelled) {
              localStorage.removeItem(V360_ACCESS_TOKEN_KEY);
              localStorage.removeItem(V360_REFRESH_TOKEN_KEY);
              tokenStore.clear();
              refreshTokenStore.clear();
              setIsAuthenticated(false);
              setIsLoading(false);
            }
          }
        } else {
          // Network error or non-401: clear tokens and mark unauthenticated
          localStorage.removeItem(V360_ACCESS_TOKEN_KEY);
          localStorage.removeItem(V360_REFRESH_TOKEN_KEY);
          tokenStore.clear();
          refreshTokenStore.clear();
          setIsAuthenticated(false);
          setIsLoading(false);
        }
      }
    };

    initialCheck();

    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── login ──────────────────────────────────────────────────────────────────
  const login = useCallback(
    async (email: string, password: string, redirectTo?: string): Promise<LoginOutcome> => {
      try {
        const { data: tokens } = await api.post<{
          access_token: string;
          refresh_token: string;
          token_type: string;
        }>("/auth/login", { email, password });

        localStorage.setItem(V360_ACCESS_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(V360_REFRESH_TOKEN_KEY, tokens.refresh_token);
        tokenStore.set(tokens.access_token);
        refreshTokenStore.set(tokens.refresh_token);

        // /me confirma que a sessão está válida antes de redirecionar
        const { data: profile } = await api.get<UserProfile>("/auth/me");
        setUser(profile);
        setIsAuthenticated(true);

        // Redirect happens here, after /me returns 200.
        // router.refresh() forces the middleware to re-evaluate the session;
        // without it the server still sees the unauthenticated state and
        // redirects back to /login in a loop.
        router.push(redirectTo ?? ROUTES.DASHBOARD);
        router.refresh();

        return { success: true };
      } catch (err: unknown) {
        const data = (err as { response?: { data?: Record<string, unknown> } })
          ?.response?.data;
        const message =
          (data?.detail as string) ||
          (data?.message as string) ||
          "Erro ao fazer login";
        return { success: false, message };
      }
    },
    [router]
  );

  // ── logout ─────────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(V360_REFRESH_TOKEN_KEY);
    try {
      if (refreshToken) {
        await api.post("/auth/logout", { refresh_token: refreshToken });
      }
    } catch {
      // Proceed with local cleanup even if the API call fails
    } finally {
      localStorage.removeItem(V360_ACCESS_TOKEN_KEY);
      localStorage.removeItem(V360_REFRESH_TOKEN_KEY);
      tokenStore.clear();
      refreshTokenStore.clear();
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
