import type { Metadata } from "next";
import { CampaignsView } from "@/features/campaigns/components/CampaignsView";

export const metadata: Metadata = {
  title: "Campanhas",
};

export default function CampaignsPage() {
  return <CampaignsView />;
}
