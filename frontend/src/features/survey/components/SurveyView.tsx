"use client";

import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { useSurvey, useSubmitSurvey } from "../hooks/useSurvey";
import { PageLoader } from "@/components/common/LoadingSpinner";
import { cn } from "@/lib/utils";
import type { SurveyResponse } from "@/types";
import { extractApiError } from "@/lib/api";

interface SurveyViewProps {
  token: string;
}

// FE-R7: Completely isolated from auth area — no identity data
export function SurveyView({ token }: SurveyViewProps) {
  const { data: survey, isLoading, error } = useSurvey(token);
  const submitMutation = useSubmitSurvey(token);
  const [submitted, setSubmitted] = useState(false);
  const [protocol, setProtocol] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <PageLoader />
      </div>
    );
  }

  if (error || !survey) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
        <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
        <h2 className="text-lg font-semibold text-gray-900 mb-2">Pesquisa não encontrada</h2>
        <p className="text-sm text-gray-500">
          Este link de pesquisa é inválido ou expirou. Por favor, solicite um novo link.
        </p>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
        <CheckCircle2 className="w-16 h-16 text-green-500 mb-6" />
        <h2 className="text-2xl font-bold text-gray-900 mb-3">Obrigado pela sua participação!</h2>
        <p className="text-base text-gray-600 max-w-sm mb-6">
          Suas respostas foram registradas de forma anônima e serão usadas para melhorar o ambiente de trabalho.
        </p>
        {protocol && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
            <p className="text-xs text-gray-500 mb-1">Protocolo de confirmação</p>
            <p className="font-mono text-sm font-medium text-gray-800">{protocol}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <SurveyForm
      survey={survey}
      token={token}
      onSubmit={async (responses) => {
        try {
          const result = await submitMutation.mutateAsync({ token, responses });
          setProtocol(result.protocol);
          setSubmitted(true);
        } catch (error) {
          toast.error(extractApiError(error).message || "Erro ao enviar respostas");
        }
      }}
      isSubmitting={submitMutation.isPending}
    />
  );
}

// Build dynamic Zod schema from survey questions
function buildSurveySchema(questions: { id: string; required: boolean; type: string }[]) {
  const shape: Record<string, z.ZodTypeAny> = {};
  questions.forEach((q) => {
    if (q.required) {
      shape[q.id] = z.string().min(1, "Esta pergunta é obrigatória");
    } else {
      shape[q.id] = z.string().optional();
    }
  });
  return z.object(shape);
}

interface SurveyFormProps {
  survey: { campaign_name: string; company_name: string; questions: { id: string; text: string; type: string; required: boolean; options?: string[]; order: number; dimension: string }[] };
  token: string;
  onSubmit: (responses: SurveyResponse[]) => Promise<void>;
  isSubmitting: boolean;
}

const LIKERT_5_OPTIONS = [
  { value: "1", label: "Nunca" },
  { value: "2", label: "Raramente" },
  { value: "3", label: "Às vezes" },
  { value: "4", label: "Frequentemente" },
  { value: "5", label: "Sempre" },
];

function SurveyForm({ survey, onSubmit, isSubmitting }: SurveyFormProps) {
  const schema = buildSurveySchema(survey.questions);
  type FormData = z.infer<typeof schema>;

  const { control, register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const handleFormSubmit = async (data: FormData) => {
    const responses: SurveyResponse[] = Object.entries(data)
      .filter(([, value]) => value !== undefined && value !== "")
      .map(([question_id, answer]) => ({
        question_id,
        answer: answer as string | number,
      }));
    await onSubmit(responses);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{survey.campaign_name}</h1>
        <p className="text-gray-500 text-sm">{survey.company_name}</p>
        <div className="mt-4 inline-flex items-center gap-2 bg-green-50 text-green-700 text-xs font-medium px-3 py-1.5 rounded-full border border-green-200">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          Pesquisa 100% anônima
        </div>
      </div>

      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
        {survey.questions
          .sort((a, b) => a.order - b.order)
          .map((question, index) => (
            <div key={question.id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start gap-3 mb-4">
                <span className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 text-primary text-xs font-semibold flex items-center justify-center">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm text-gray-400 mb-1">{question.dimension}</p>
                  <p className="text-base font-medium text-gray-900">
                    {question.text}
                    {question.required && (
                      <span className="text-red-500 ml-1" aria-hidden="true">*</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Likert 5 — uses Controller so selection state is always visible */}
              {question.type === "LIKERT_5" && (
                <Controller
                  name={question.id}
                  control={control}
                  render={({ field }) => (
                    <div className="grid grid-cols-5 gap-2" role="radiogroup">
                      {LIKERT_5_OPTIONS.map((option) => {
                        const selected = field.value === option.value;
                        return (
                          <button
                            key={option.value}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            onClick={() => field.onChange(option.value)}
                            className={cn(
                              "flex flex-col items-center gap-1.5 py-2 px-1 rounded-lg border-2 transition-all cursor-pointer",
                              selected
                                ? "border-primary bg-primary text-white"
                                : "border-gray-200 text-gray-500 hover:border-primary/50 hover:text-primary"
                            )}
                          >
                            <span className="text-sm font-semibold">{option.value}</span>
                            <span className="text-xs leading-tight text-center">{option.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                />
              )}

              {/* Text */}
              {question.type === "TEXT" && (
                <textarea
                  {...register(question.id)}
                  rows={3}
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none"
                  placeholder="Sua resposta..."
                />
              )}

              {/* Multiple Choice */}
              {question.type === "MULTIPLE_CHOICE" && question.options && (
                <div className="space-y-2">
                  {question.options.map((option) => (
                    <label key={option} className="flex items-center gap-2.5 cursor-pointer">
                      <input
                        type="radio"
                        value={option}
                        {...register(question.id)}
                        className="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                      />
                      <span className="text-sm text-gray-700">{option}</span>
                    </label>
                  ))}
                </div>
              )}

              {/* Yes/No */}
              {question.type === "YES_NO" && (
                <Controller
                  name={question.id}
                  control={control}
                  render={({ field }) => (
                    <div className="flex gap-3">
                      {["Sim", "Não"].map((option) => {
                        const selected = field.value === option;
                        return (
                          <button
                            key={option}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            onClick={() => field.onChange(option)}
                            className={cn(
                              "px-5 py-2 rounded-lg border-2 text-sm font-medium transition-all",
                              selected
                                ? "border-primary bg-primary text-white"
                                : "border-gray-200 text-gray-600 hover:border-primary/50 hover:text-primary"
                            )}
                          >
                            {option}
                          </button>
                        );
                      })}
                    </div>
                  )}
                />
              )}

              {errors[question.id] && (
                <p className="mt-2 text-xs text-red-600" role="alert">
                  {String((errors[question.id] as { message?: string })?.message || "Campo obrigatório")}
                </p>
              )}
            </div>
          ))}

        <div className="pb-8">
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 px-6 bg-primary text-white font-semibold rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isSubmitting ? "Enviando..." : "Enviar Respostas"}
          </button>
          <p className="text-center text-xs text-gray-400 mt-3">
            Suas respostas são completamente anônimas e protegidas.
          </p>
        </div>
      </form>
    </div>
  );
}
