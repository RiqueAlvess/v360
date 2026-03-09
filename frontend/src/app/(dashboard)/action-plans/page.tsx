import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ClipboardList } from "lucide-react";

export const metadata: Metadata = { title: "Planos de Ação" };

export default function ActionPlansPage() {
  return (
    <div>
      <PageHeader
        title="Planos de Ação"
        description="Gerencie os planos de ação pós-diagnóstico NR-1"
        breadcrumbs={[{ label: "Planos de Ação" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200">
        <EmptyState
          title="Módulo de Planos de Ação"
          description="Crie planos de ação baseados nos resultados das pesquisas para mitigar riscos identificados."
          icon={ClipboardList}
        />
      </div>
    </div>
  );
}
