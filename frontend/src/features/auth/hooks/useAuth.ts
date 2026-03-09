"use client";

import { create } from "zustand";
import { tokenStore } from "@/lib/api";
import { authService } from "../services/authService";
import type { AuthStore } from "../types/auth.types";
import type { UserProfile } from "@/types";

// Zustand store for auth state (FE-R4: token in memory, not localStorage)
export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: (user: UserProfile, accessToken: string) => {
    tokenStore.set(accessToken);
    set({ user, accessToken, isAuthenticated: true, isLoading: false });
  },

  setAccessToken: (token: string) => {
    tokenStore.set(token);
    set({ accessToken: token });
  },

  clearAuth: () => {
    tokenStore.clear();
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },
}));

/**
 * Hook for auth actions (login, logout)
 */
export function useAuth() {
  const { user, isAuthenticated, isLoading, setAuth, clearAuth, setLoading } = useAuthStore();

  const login = async (email: string, password: string, rememberMe = false) => {
    setLoading(true);
    try {
      const response = await authService.login({ email, password, remember_me: rememberMe });
      setAuth(response.user, response.access_token);
      return response;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await authService.logout();
    } catch {
      // Logout even if the API call fails
    } finally {
      clearAuth();
    }
  };

  const refreshSession = async () => {
    try {
      const profile = await authService.getProfile();
      // If we can get profile, refresh token was used by interceptor
      useAuthStore.getState().setAuth(
        profile,
        useAuthStore.getState().accessToken ?? ""
      );
    } catch {
      clearAuth();
    }
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    refreshSession,
  };
}
