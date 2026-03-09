"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Shield, CheckCircle2 } from "lucide-react";
import api from "@/lib/api";
import { extractApiError } from "@/lib/api";

const whistleblowerSchema = z.object({
  category: z.string().min(1, "Categoria é obrigatória"),
  description: z
    .string()
    .min(20, "Descrição deve ter pelo menos 20 caracteres")
    .max(2000, "Descrição muito longa"),
  isAnonymous: z.boolean().default(true),
  contactEmail: z.string().email("E-mail inválido").optional().or(z.literal("")),
});

type FormData = z.infer<typeof whistleblowerSchema>;

const CATEGORIES = [
  "Assédio Moral",
  "Assédio Sexual",
  "Discriminação",
  "Violência no Trabalho",
  "Condições Insalubres",
  "Irregularidades Financeiras",
  "Violação de Privacidade",
  "Outros",
];

// FE-R7: No identity data mixed with complaint data
export function WhistleblowerForm() {
  const [submitted, setSubmitted] = useState(false);
  const [protocol, setProtocol] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(whistleblowerSchema),
    defaultValues: { isAnonymous: true },
  });

  const isAnonymous = watch("isAnonymous");

  const onSubmit = async (data: FormData) => {
    try {
      const payload = {
        category: data.category,
        description: data.description,
        is_anonymous: data.isAnonymous,
        ...(data.isAnonymous ? {} : { contact_email: data.contactEmail }),
      };
      const response = await api.post<{ protocol: string }>("/whistleblower", payload);
      setProtocol(response.data.protocol);
      setSubmitted(true);
    } catch (error) {
      toast.error(extractApiError(error).message || "Erro ao enviar denúncia");
    }
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
        <CheckCircle2 className="w-16 h-16 text-green-500 mb-6" />
        <h2 className="text-2xl font-bold text-gray-900 mb-3">Denúncia registrada!</h2>
        <p className="text-base text-gray-600 max-w-sm mb-6">
          Sua denúncia foi recebida e será analisada. Guarde seu protocolo para acompanhamento.
        </p>
        {protocol && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-6 py-4">
            <p className="text-xs text-gray-500 mb-1">Número do protocolo</p>
            <p className="font-mono text-xl font-bold text-gray-900 tracking-widest">{protocol}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
          <Shield className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Canal de Denúncias</h1>
        <p className="text-sm text-gray-500">
          Este canal é seguro e confidencial. Você pode fazer sua denúncia de forma anônima.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {/* Categoria */}
        <div>
          <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
            Categoria da denúncia <span className="text-red-500">*</span>
          </label>
          <select
            id="category"
            {...register("category")}
            className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          >
            <option value="">Selecione uma categoria</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
          {errors.category && (
            <p className="mt-1 text-xs text-red-600">{errors.category.message}</p>
          )}
        </div>

        {/* Descrição */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
            Descrição <span className="text-red-500">*</span>
          </label>
          <textarea
            id="description"
            rows={5}
            {...register("description")}
            className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none"
            placeholder="Descreva detalhadamente o que aconteceu, quando, onde e quem estava envolvido..."
          />
          {errors.description && (
            <p className="mt-1 text-xs text-red-600">{errors.description.message}</p>
          )}
        </div>

        {/* Anonimidade */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              {...register("isAnonymous")}
              className="mt-0.5 w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary/30"
            />
            <div>
              <span className="text-sm font-medium text-gray-800">Manter identidade anônima</span>
              <p className="text-xs text-gray-500 mt-0.5">
                Sua identidade não será associada à denúncia em nenhuma circunstância.
              </p>
            </div>
          </label>
        </div>

        {/* Contato opcional */}
        {!isAnonymous && (
          <div>
            <label htmlFor="contactEmail" className="block text-sm font-medium text-gray-700 mb-1">
              E-mail para contato (opcional)
            </label>
            <input
              id="contactEmail"
              type="email"
              {...register("contactEmail")}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              placeholder="seuemail@exemplo.com"
            />
            {errors.contactEmail && (
              <p className="mt-1 text-xs text-red-600">{errors.contactEmail.message}</p>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-3 px-6 bg-primary text-white font-semibold rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-60"
        >
          {isSubmitting ? "Enviando..." : "Enviar Denúncia"}
        </button>

        <p className="text-center text-xs text-gray-400">
          Esta denúncia é tratada com total confidencialidade conforme a Lei 9.029/95 e NR-1.
        </p>
      </form>
    </div>
  );
}
