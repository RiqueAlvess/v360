import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
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
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <FileBarChart className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve você poderá gerar relatórios completos de conformidade NR-1 em PDF, DOCX e XLSX a partir das campanhas encerradas.
          </p>
        </div>
      </div>
    </div>
  );
}
