import type { Metadata } from "next";

export const metadata: Metadata = { title: "Editar Campanha" };

interface EditCampaignPageProps {
  params: { id: string };
}

export default function EditCampaignPage({ params }: EditCampaignPageProps) {
  // Dynamic import to avoid SSR issues with form components
  const { id } = params;

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">Editando campanha: {id}</p>
    </div>
  );
}
