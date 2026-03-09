import api from "@/lib/api";
import type { LoginRequest, LoginResponse, RefreshResponse, UserProfile } from "@/types";

export const authService = {
  /**
   * Authenticate user with email and password
   */
  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>("/auth/login", data);
    return response.data;
  },

  /**
   * Logout the current user
   */
  async logout(): Promise<void> {
    await api.post("/auth/logout");
  },

  /**
   * Refresh the access token using the httpOnly refresh token cookie
   */
  async refresh(): Promise<RefreshResponse> {
    const response = await api.post<RefreshResponse>("/auth/refresh");
    return response.data;
  },

  /**
   * Get the current user profile
   */
  async getProfile(): Promise<UserProfile> {
    const response = await api.get<UserProfile>("/auth/me");
    return response.data;
  },

  /**
   * Request a password reset OTP for the given email
   */
  async requestPasswordReset(email: string): Promise<void> {
    await api.post("/auth/password-reset/request", { email });
  },

  /**
   * Verify the OTP code for password reset
   */
  async verifyOtp(email: string, code: string): Promise<{ reset_token: string }> {
    const response = await api.post<{ reset_token: string }>("/auth/password-reset/verify", {
      email,
      code,
    });
    return response.data;
  },

  /**
   * Set a new password using the reset token
   */
  async resetPassword(resetToken: string, newPassword: string): Promise<void> {
    await api.post("/auth/password-reset/confirm", {
      reset_token: resetToken,
      new_password: newPassword,
    });
  },
};
