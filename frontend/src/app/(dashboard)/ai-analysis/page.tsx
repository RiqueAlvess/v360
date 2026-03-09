import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { Brain } from "lucide-react";

export const metadata: Metadata = { title: "Análise IA" };

export default function AiAnalysisPage() {
  return (
    <div>
      <PageHeader
        title="Análise por Inteligência Artificial"
        description="Visualize análises geradas por IA para cada campanha"
        breadcrumbs={[{ label: "Análise IA" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200">
        <EmptyState
          title="Módulo de Análise IA"
          description="Selecione uma campanha para visualizar a análise gerada automaticamente pelo modelo de IA via OpenRouter."
          icon={Brain}
        />
      </div>
    </div>
  );
}
