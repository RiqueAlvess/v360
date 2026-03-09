import type { Metadata } from "next";
import { SurveyView } from "@/features/survey/components/SurveyView";

export const metadata: Metadata = {
  title: "Pesquisa de Bem-Estar",
  description: "Pesquisa anônima de riscos psicossociais",
  robots: { index: false, follow: false },
};

interface SurveyPageProps {
  params: { token: string };
}

// FE-R7: This route has NO shared layout with the authenticated area
export default function SurveyPage({ params }: SurveyPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <SurveyView token={params.token} />
    </div>
  );
}
