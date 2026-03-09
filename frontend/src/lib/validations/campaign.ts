import { z } from "zod";

export const campaignSchema = z.object({
  name: z
    .string()
    .min(3, "Nome deve ter pelo menos 3 caracteres")
    .max(200, "Nome muito longo"),
  description: z.string().max(1000, "Descrição muito longa").optional(),
  startDate: z.string().min(1, "Data de início é obrigatória"),
  endDate: z.string().min(1, "Data de término é obrigatória"),
  targetAudience: z.string().min(1, "Público-alvo é obrigatório"),
  anonymousResponses: z.boolean().default(true),
  reminderDays: z.number().int().min(1).max(30).optional(),
});

export type CampaignFormData = z.infer<typeof campaignSchema>;

export const actionPlanSchema = z.object({
  title: z
    .string()
    .min(3, "Título deve ter pelo menos 3 caracteres")
    .max(200, "Título muito longo"),
  description: z.string().min(10, "Descrição deve ter pelo menos 10 caracteres"),
  responsibleId: z.string().uuid("Responsável inválido"),
  dueDate: z.string().min(1, "Data limite é obrigatória"),
  priority: z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
  status: z.enum(["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"]).optional(),
});

export type ActionPlanFormData = z.infer<typeof actionPlanSchema>;
