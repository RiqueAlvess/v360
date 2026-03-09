import type { Metadata } from "next";
import { CampaignDetailView } from "@/features/campaigns/components/CampaignDetailView";

export const metadata: Metadata = { title: "Detalhes da Campanha" };

interface CampaignDetailPageProps {
  params: { id: string };
}

export default function CampaignDetailPage({ params }: CampaignDetailPageProps) {
  return <CampaignDetailView id={params.id} />;
}
