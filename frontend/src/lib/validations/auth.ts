import { z } from "zod";

export const loginSchema = z.object({
  email: z
    .string()
    .min(1, "E-mail é obrigatório")
    .email("E-mail inválido")
    .transform((v) => v.toLowerCase()),
  password: z.string().min(8, "Senha deve ter pelo menos 8 caracteres"),
  rememberMe: z.boolean().optional().default(false),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const resetPasswordRequestSchema = z.object({
  email: z
    .string()
    .min(1, "E-mail é obrigatório")
    .email("E-mail inválido")
    .transform((v) => v.toLowerCase()),
});

export type ResetPasswordRequestData = z.infer<typeof resetPasswordRequestSchema>;

export const resetPasswordOtpSchema = z.object({
  code: z
    .string()
    .length(6, "Código deve ter 6 dígitos")
    .regex(/^\d{6}$/, "Código deve conter apenas números"),
});

export type ResetPasswordOtpData = z.infer<typeof resetPasswordOtpSchema>;

export const resetPasswordNewSchema = z
  .object({
    password: z
      .string()
      .min(8, "Senha deve ter pelo menos 8 caracteres")
      .regex(/[A-Z]/, "Senha deve conter pelo menos uma letra maiúscula")
      .regex(/[0-9]/, "Senha deve conter pelo menos um número"),
    confirmPassword: z.string().min(1, "Confirmação de senha é obrigatória"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Senhas não conferem",
    path: ["confirmPassword"],
  });

export type ResetPasswordNewData = z.infer<typeof resetPasswordNewSchema>;
