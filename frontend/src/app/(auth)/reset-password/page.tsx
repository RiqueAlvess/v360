import type { Metadata } from "next";
import { ResetPasswordForm } from "@/features/auth/components/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Recuperar Senha",
};

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-dark to-primary flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">VIVAMENTE 360°</h1>
          <p className="mt-2 text-blue-200 text-sm">Recuperação de senha</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <ResetPasswordForm />
        </div>
      </div>
    </div>
  );
}
