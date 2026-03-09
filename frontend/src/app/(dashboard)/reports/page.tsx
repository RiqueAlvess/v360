import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { FileBarChart } from "lucide-react";

export const metadata: Metadata = { title: "Relatórios" };

export default function ReportsPage() {
  return (
    <div>
      <PageHeader
        title="Relatórios NR-1"
        description="Gere relatórios PDF, DOCX e XLSX com dados de conformidade"
        breadcrumbs={[{ label: "Relatórios" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200">
        <EmptyState
          title="Módulo de Relatórios"
          description="Selecione uma campanha e gere relatórios completos para conformidade NR-1."
          icon={FileBarChart}
        />
      </div>
    </div>
  );
}
