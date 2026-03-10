"use client";

// Re-export the canonical auth hook from the shared context so that all
// feature-level imports continue to work without path changes.
export { useAuth } from "@/contexts/AuthContext";
export type { AuthContextValue, LoginOutcome, LoginResult, LoginError } from "@/contexts/AuthContext";
