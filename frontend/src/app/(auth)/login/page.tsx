import type { Metadata } from "next";
import { LoginForm } from "@/features/auth/components/LoginForm";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Acesse sua conta VIVAMENTE 360°",
};

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-dark to-primary flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">VIVAMENTE 360°</h1>
          <p className="mt-2 text-blue-200 text-sm">
            Gestão de Riscos Psicossociais — NR-1
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Bem-vindo de volta</h2>
          <p className="text-sm text-gray-500 mb-6">Entre com suas credenciais para acessar</p>
          <LoginForm />
        </div>

        <p className="text-center mt-6 text-xs text-blue-200">
          © {new Date().getFullYear()} VIVAMENTE. Todos os direitos reservados.
        </p>
      </div>
    </div>
  );
}
