"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { ROUTES } from "@/lib/constants";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push(ROUTES.LOGIN);
    }
  }, [isLoading, isAuthenticated, router]);

  // Bloqueia qualquer renderização enquanto o estado de auth não for conhecido
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <LoadingSpinner size="lg" label="Verificando sessão..." />
      </div>
    );
  }

  // Usuário não autenticado: não renderiza nada (o useEffect faz o redirect)
  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
