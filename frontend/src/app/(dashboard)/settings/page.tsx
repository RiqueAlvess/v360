import type { Metadata } from "next";
import { PageHeader } from "@/components/common/PageHeader";

export const metadata: Metadata = { title: "Configurações" };

export default function SettingsPage() {
  return (
    <div>
      <PageHeader
        title="Configurações"
        description="Gerencie as configurações da sua conta e organização"
        breadcrumbs={[{ label: "Configurações" }]}
      />
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        <SettingsSection title="Perfil" description="Informações pessoais e de acesso" />
        <SettingsSection title="Organização" description="Dados da empresa e configurações gerais" />
        <SettingsSection title="Notificações" description="Preferências de notificações por e-mail" />
        <SettingsSection title="Segurança" description="Senha e autenticação" />
      </div>
    </div>
  );
}

function SettingsSection({ title, description }: { title: string; description: string }) {
  return (
    <div className="px-6 py-4 flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
      </div>
      <button className="text-sm text-primary hover:text-primary-dark font-medium">
        Editar
      </button>
    </div>
  );
}
