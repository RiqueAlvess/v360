import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { MessageSquareWarning } from "lucide-react";

export const metadata: Metadata = { title: "Canal de Denúncias" };

export default function WhistleblowerAdminPage() {
  return (
    <div>
      <PageHeader
        title="Canal de Denúncias"
        description="Gerencie e acompanhe as denúncias recebidas"
        breadcrumbs={[{ label: "Canal de Denúncias" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200">
        <EmptyState
          title="Nenhuma denúncia registrada"
          description="As denúncias recebidas pelo canal anônimo aparecerão aqui."
          icon={MessageSquareWarning}
        />
      </div>
    </div>
  );
}
