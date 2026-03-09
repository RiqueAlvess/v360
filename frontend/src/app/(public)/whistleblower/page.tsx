import type { Metadata } from "next";
import { WhistleblowerForm } from "@/features/whistleblower/components/WhistleblowerForm";

export const metadata: Metadata = {
  title: "Canal de Denúncias",
  description: "Canal anônimo e seguro para relatar irregularidades",
  robots: { index: false, follow: false },
};

// FE-R7: Completely isolated route — no auth, no company identity
export default function WhistleblowerPublicPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <WhistleblowerForm />
    </div>
  );
}
