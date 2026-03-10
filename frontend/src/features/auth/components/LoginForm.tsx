"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { loginSchema, type LoginFormData } from "@/lib/validations/auth";
import { useAuth } from "../hooks/useAuth";
import { ROUTES } from "@/lib/constants";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated, isLoading } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Se já estiver autenticado ao montar, redireciona imediatamente
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push(ROUTES.DASHBOARD);
    }
  }, [isLoading, isAuthenticated, router]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
      rememberMe: false,
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setApiError(null);
    const callbackUrl = searchParams.get("callbackUrl") || ROUTES.DASHBOARD;
    // O redirect acontece dentro de login() após /me retornar 200
    const result = await login(data.email, data.password, callbackUrl);
    if (!result.success) {
      const message =
        result.message === "Incorrect email or password" ||
        result.message?.toLowerCase().includes("senha") ||
        result.message?.toLowerCase().includes("password")
          ? "E-mail ou senha incorretos"
          : result.message || "Erro ao fazer login";
      setApiError(message);
    }
  };

  const isProcessing = isSubmitting || isLoading;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          E-mail
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          autoFocus
          {...register("email")}
          className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors disabled:opacity-50"
          placeholder="seuemail@empresa.com"
          disabled={isProcessing}
          aria-describedby={errors.email ? "email-error" : undefined}
          aria-invalid={!!errors.email}
        />
        {errors.email && (
          <p id="email-error" className="mt-1 text-xs text-red-600" role="alert">
            {errors.email.message}
          </p>
        )}
      </div>

      {/* Password */}
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
          Senha
        </label>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            {...register("password")}
            className="w-full px-3 py-2.5 pr-10 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors disabled:opacity-50"
            placeholder="••••••••"
            disabled={isProcessing}
            aria-describedby={errors.password ? "password-error" : undefined}
            aria-invalid={!!errors.password}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {errors.password && (
          <p id="password-error" className="mt-1 text-xs text-red-600" role="alert">
            {errors.password.message}
          </p>
        )}
      </div>

      {/* Remember me + Forgot password */}
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            {...register("rememberMe")}
            className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary/30"
            disabled={isProcessing}
          />
          <span className="text-sm text-gray-600">Lembrar-me</span>
        </label>
        <Link
          href={ROUTES.RESET_PASSWORD}
          className="text-sm text-primary hover:text-primary-dark transition-colors"
        >
          Esqueci a senha
        </Link>
      </div>

      {/* Erro da API */}
      {apiError && (
        <p className="text-sm text-red-600 text-center" role="alert">
          {apiError}
        </p>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isProcessing}
        className="w-full py-2.5 px-4 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {isProcessing ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            Entrando...
          </>
        ) : (
          "Entrar"
        )}
      </button>
    </form>
  );
}
