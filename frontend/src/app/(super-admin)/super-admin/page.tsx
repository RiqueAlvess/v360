import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { Building2 } from "lucide-react";

export const metadata: Metadata = { title: "Super Admin" };

// This route is protected by middleware — only super_admin role can access
export default function SuperAdminPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        <PageHeader
          title="Painel Super Admin"
          description="Gestão global de tenants e monitoramento do sistema"
          breadcrumbs={[{ label: "Super Admin" }]}
        />
        <div className="bg-white rounded-xl border border-gray-200">
          <EmptyState
            title="Painel de Controle Global"
            description="Gerencie todas as empresas, usuários e monitore o sistema VIVAMENTE 360°."
            icon={Building2}
          />
        </div>
      </div>
    </div>
  );
}
