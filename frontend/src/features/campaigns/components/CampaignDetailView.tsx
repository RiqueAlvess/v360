"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Edit, Play, Square, Copy } from "lucide-react";
import { useCampaign, useActivateCampaign, useCloseCampaign } from "../hooks/useCampaigns";
import { PageHeader } from "@/components/common/PageHeader";
import { CampaignStatusBadge } from "@/components/common/StatusBadge";
import { PageLoader } from "@/components/common/LoadingSpinner";
import { formatDate, formatPercent } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";
import { extractApiError } from "@/lib/api";

interface CampaignDetailViewProps {
  id: string;
}

export function CampaignDetailView({ id }: CampaignDetailViewProps) {
  const router = useRouter();
  const { data: campaign, isLoading } = useCampaign(id);
  const activateMutation = useActivateCampaign();
  const closeMutation = useCloseCampaign();

  if (isLoading) return <PageLoader />;

  if (!campaign) {
    return (
      <div className="text-center py-16 text-gray-500">Campanha não encontrada.</div>
    );
  }

  const handleActivate = async () => {
    try {
      await activateMutation.mutateAsync(id);
      toast.success("Campanha ativada!");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  const handleClose = async () => {
    try {
      await closeMutation.mutateAsync(id);
      toast.success("Campanha encerrada.");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  const surveyUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/survey/${campaign.survey_token}`;

  return (
    <div className="space-y-6">
      <PageHeader
        title={campaign.name}
        breadcrumbs={[
          { label: "Campanhas", href: ROUTES.CAMPAIGNS },
          { label: campaign.name },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Voltar
            </button>
            {campaign.status === "DRAFT" && (
              <button
                onClick={() => router.push(`${ROUTES.CAMPAIGNS}/${id}/edit`)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Edit className="w-4 h-4" />
                Editar
              </button>
            )}
            {campaign.status === "DRAFT" && (
              <button
                onClick={handleActivate}
                disabled={activateMutation.isPending}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-60"
              >
                <Play className="w-4 h-4" />
                Ativar Campanha
              </button>
            )}
            {campaign.status === "ACTIVE" && (
              <button
                onClick={handleClose}
                disabled={closeMutation.isPending}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-60"
              >
                <Square className="w-4 h-4" />
                Encerrar Campanha
              </button>
            )}
          </div>
        }
      />

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InfoCard label="Status" value={<CampaignStatusBadge status={campaign.status} />} />
        <InfoCard label="Período" value={`${formatDate(campaign.start_date)} – ${formatDate(campaign.end_date)}`} />
        <InfoCard
          label="Respostas"
          value={`${campaign.response_count} (${formatPercent(campaign.completion_rate)})`}
        />
      </div>

      {/* Description */}
      {campaign.description && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Descrição</h3>
          <p className="text-sm text-gray-600">{campaign.description}</p>
        </div>
      )}

      {/* Survey Link */}
      {campaign.status === "ACTIVE" && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Link da Pesquisa (Blind Drop)</h3>
          <div className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
            <p className="flex-1 text-sm font-mono text-gray-600 truncate">{surveyUrl}</p>
            <button
              onClick={() => {
                void navigator.clipboard.writeText(surveyUrl);
                toast.success("Link copiado!");
              }}
              className="flex-shrink-0 p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors"
              aria-label="Copiar link"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Este link pode ser compartilhado com colaboradores. As respostas são completamente anônimas.
          </p>
        </div>
      )}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <p className="text-xs text-gray-500 mb-1.5">{label}</p>
      <div className="text-sm font-medium text-gray-900">{value}</div>
    </div>
  );
}
