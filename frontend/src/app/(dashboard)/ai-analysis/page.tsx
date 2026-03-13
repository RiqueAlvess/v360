import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
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
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <Brain className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve o sistema gerará análises automáticas dos resultados de cada campanha usando inteligência artificial.
          </p>
        </div>
      </div>
    </div>
  );
}
