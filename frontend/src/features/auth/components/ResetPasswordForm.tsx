"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import {
  resetPasswordRequestSchema,
  resetPasswordOtpSchema,
  resetPasswordNewSchema,
  type ResetPasswordRequestData,
  type ResetPasswordOtpData,
  type ResetPasswordNewData,
} from "@/lib/validations/auth";
import { authService } from "../services/authService";
import { ROUTES } from "@/lib/constants";
import { extractApiError } from "@/lib/api";

type Step = "email" | "otp" | "newPassword" | "success";

export function ResetPasswordForm() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");

  // Step 1: Email form
  const emailForm = useForm<ResetPasswordRequestData>({
    resolver: zodResolver(resetPasswordRequestSchema),
  });

  // Step 2: OTP form
  const otpForm = useForm<ResetPasswordOtpData>({
    resolver: zodResolver(resetPasswordOtpSchema),
  });

  // Step 3: New password form
  const passwordForm = useForm<ResetPasswordNewData>({
    resolver: zodResolver(resetPasswordNewSchema),
  });

  const stepLabels = ["E-mail", "Código", "Nova Senha"];
  const currentStepIndex = step === "email" ? 0 : step === "otp" ? 1 : step === "newPassword" ? 2 : 3;

  const handleEmailSubmit = async (data: ResetPasswordRequestData) => {
    try {
      await authService.requestPasswordReset(data.email);
      setEmail(data.email);
      setStep("otp");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  const handleOtpSubmit = async (data: ResetPasswordOtpData) => {
    try {
      const result = await authService.verifyOtp(email, data.code);
      setResetToken(result.reset_token);
      setStep("newPassword");
    } catch (error) {
      const err = extractApiError(error);
      toast.error(err.status === 400 ? "Código inválido ou expirado" : err.message);
    }
  };

  const handlePasswordSubmit = async (data: ResetPasswordNewData) => {
    try {
      await authService.resetPassword(resetToken, data.password);
      setStep("success");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  if (step === "success") {
    return (
      <div className="text-center">
        <CheckCircle2 className="w-14 h-14 text-green-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Senha redefinida!</h2>
        <p className="text-sm text-gray-500 mb-6">
          Sua senha foi alterada com sucesso. Você já pode entrar com a nova senha.
        </p>
        <button
          onClick={() => router.push(ROUTES.LOGIN)}
          className="w-full py-2.5 px-4 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors"
        >
          Ir para o login
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Step indicator */}
      {currentStepIndex < 3 && (
        <div className="flex items-center gap-2 mb-6">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
                  i < currentStepIndex
                    ? "bg-primary text-white"
                    : i === currentStepIndex
                    ? "bg-primary text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                {i < currentStepIndex ? "✓" : i + 1}
              </div>
              <span className={`text-xs ${i === currentStepIndex ? "text-gray-900 font-medium" : "text-gray-400"}`}>
                {label}
              </span>
              {i < stepLabels.length - 1 && (
                <div className={`flex-1 h-px ${i < currentStepIndex ? "bg-primary" : "bg-gray-200"}`} />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Step 1: Email */}
      {step === "email" && (
        <>
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Recuperar senha</h2>
          <p className="text-sm text-gray-500 mb-6">
            Informe seu e-mail para receber o código de verificação.
          </p>
          <form onSubmit={emailForm.handleSubmit(handleEmailSubmit)} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                E-mail
              </label>
              <input
                id="email"
                type="email"
                autoFocus
                {...emailForm.register("email")}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                placeholder="seuemail@empresa.com"
              />
              {emailForm.formState.errors.email && (
                <p className="mt-1 text-xs text-red-600">
                  {emailForm.formState.errors.email.message}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={emailForm.formState.isSubmitting}
              className="w-full py-2.5 px-4 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60"
            >
              {emailForm.formState.isSubmitting ? "Enviando..." : "Enviar código"}
            </button>
          </form>
        </>
      )}

      {/* Step 2: OTP */}
      {step === "otp" && (
        <>
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Verifique seu e-mail</h2>
          <p className="text-sm text-gray-500 mb-6">
            Enviamos um código de 6 dígitos para <strong>{email}</strong>.
          </p>
          <form onSubmit={otpForm.handleSubmit(handleOtpSubmit)} className="space-y-4">
            <div>
              <label htmlFor="code" className="block text-sm font-medium text-gray-700 mb-1">
                Código de verificação
              </label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                autoFocus
                {...otpForm.register("code")}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-center tracking-widest font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                placeholder="000000"
              />
              {otpForm.formState.errors.code && (
                <p className="mt-1 text-xs text-red-600">
                  {otpForm.formState.errors.code.message}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={otpForm.formState.isSubmitting}
              className="w-full py-2.5 px-4 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60"
            >
              {otpForm.formState.isSubmitting ? "Verificando..." : "Verificar código"}
            </button>
            <button
              type="button"
              onClick={() => setStep("email")}
              className="w-full flex items-center justify-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Voltar
            </button>
          </form>
        </>
      )}

      {/* Step 3: New Password */}
      {step === "newPassword" && (
        <>
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Defina a nova senha</h2>
          <p className="text-sm text-gray-500 mb-6">
            Sua senha deve ter pelo menos 8 caracteres, uma letra maiúscula e um número.
          </p>
          <form onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Nova senha
              </label>
              <input
                id="password"
                type="password"
                autoFocus
                {...passwordForm.register("password")}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                placeholder="••••••••"
              />
              {passwordForm.formState.errors.password && (
                <p className="mt-1 text-xs text-red-600">
                  {passwordForm.formState.errors.password.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                Confirmar nova senha
              </label>
              <input
                id="confirmPassword"
                type="password"
                {...passwordForm.register("confirmPassword")}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                placeholder="••••••••"
              />
              {passwordForm.formState.errors.confirmPassword && (
                <p className="mt-1 text-xs text-red-600">
                  {passwordForm.formState.errors.confirmPassword.message}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={passwordForm.formState.isSubmitting}
              className="w-full py-2.5 px-4 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60"
            >
              {passwordForm.formState.isSubmitting ? "Salvando..." : "Redefinir senha"}
            </button>
          </form>
        </>
      )}

      {/* Back to login */}
      {step === "email" && (
        <div className="mt-4 text-center">
          <Link href={ROUTES.LOGIN} className="text-sm text-primary hover:text-primary-dark">
            Voltar para o login
          </Link>
        </div>
      )}
    </div>
  );
}
