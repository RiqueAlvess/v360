import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
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
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <MessageSquareWarning className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve você poderá visualizar, responder e acompanhar as denúncias recebidas pelo canal anônimo.
          </p>
        </div>
      </div>
    </div>
  );
}
