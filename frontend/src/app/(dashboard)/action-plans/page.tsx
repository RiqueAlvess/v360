import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
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
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <ClipboardList className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve você poderá criar e acompanhar planos de ação para mitigar os riscos identificados nas pesquisas.
          </p>
        </div>
      </div>
    </div>
  );
}
