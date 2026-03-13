import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { HardDrive } from "lucide-react";

export const metadata: Metadata = { title: "Armazenamento" };

export default function StoragePage() {
  return (
    <div>
      <PageHeader
        title="Armazenamento"
        description="Gerencie arquivos armazenados no Cloudflare R2"
        breadcrumbs={[{ label: "Armazenamento" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <HardDrive className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve você poderá gerenciar arquivos de evidência e documentos vinculados às campanhas e planos de ação.
          </p>
        </div>
      </div>
    </div>
  );
}
