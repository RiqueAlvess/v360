import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";
import { Settings } from "lucide-react";

export const metadata: Metadata = { title: "Configurações" };

export default function SettingsPage() {
  return (
    <div>
      <PageHeader
        title="Configurações"
        description="Gerencie as configurações da sua conta e organização"
        breadcrumbs={[{ label: "Configurações" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200 p-12 flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center">
          <Settings className="w-7 h-7 text-gray-400" />
        </div>
        <div>
          <p className="text-base font-semibold text-gray-700">Módulo em desenvolvimento</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Em breve você poderá gerenciar perfil, dados da organização, notificações e segurança da conta.
          </p>
        </div>
      </div>
    </div>
  );
}
