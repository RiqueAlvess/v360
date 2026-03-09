"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-64 text-center p-6">
      <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
      <h2 className="text-lg font-semibold text-gray-900 mb-2">Erro ao carregar dashboard</h2>
      <p className="text-sm text-gray-500 mb-4 max-w-sm">
        Ocorreu um erro ao carregar os dados. Tente novamente.
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors"
      >
        Tentar novamente
      </button>
    </div>
  );
}
