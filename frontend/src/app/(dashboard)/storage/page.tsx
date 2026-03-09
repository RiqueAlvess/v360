import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
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
      <div className="bg-white rounded-xl border border-gray-200">
        <EmptyState
          title="Nenhum arquivo enviado"
          description="Faça upload de arquivos relacionados às suas campanhas e análises NR-1."
          icon={HardDrive}
        />
      </div>
    </div>
  );
}
