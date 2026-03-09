"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Play, Square, Trash2, ExternalLink, Eye } from "lucide-react";
import { useCampaigns, useDeleteCampaign, useActivateCampaign, useCloseCampaign } from "../hooks/useCampaigns";
import { PageHeader } from "@/components/common/PageHeader";
import { DataTable, type Column } from "@/components/common/DataTable";
import { CampaignStatusBadge } from "@/components/common/StatusBadge";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { usePagination } from "@/hooks/usePagination";
import { formatDate, formatPercent } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";
import type { Campaign } from "@/types";
import { extractApiError } from "@/lib/api";

export function CampaignsView() {
  const router = useRouter();
  const pagination = usePagination();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading } = useCampaigns(pagination.getQueryParams());
  const deleteMutation = useDeleteCampaign();
  const activateMutation = useActivateCampaign();
  const closeMutation = useCloseCampaign();

  const columns: Column<Campaign>[] = [
    {
      key: "name",
      header: "Nome",
      cell: (row) => (
        <div>
          <p className="font-medium text-gray-900">{row.name}</p>
          {row.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{row.description}</p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <CampaignStatusBadge status={row.status} />,
      className: "w-32",
    },
    {
      key: "dates",
      header: "Período",
      cell: (row) => (
        <span className="text-sm text-gray-600">
          {formatDate(row.start_date)} – {formatDate(row.end_date)}
        </span>
      ),
      className: "w-48",
    },
    {
      key: "responses",
      header: "Respostas",
      cell: (row) => (
        <div className="text-sm">
          <span className="font-medium text-gray-900">{row.response_count}</span>
          <span className="text-gray-500 ml-1">
            ({formatPercent(row.completion_rate)})
          </span>
        </div>
      ),
      className: "w-32",
    },
    {
      key: "actions",
      header: "Ações",
      cell: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => router.push(`${ROUTES.CAMPAIGNS}/${row.id}`)}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
            aria-label="Ver campanha"
            title="Ver detalhes"
          >
            <Eye className="w-4 h-4" />
          </button>

          {row.status === "DRAFT" && (
            <button
              onClick={() => handleActivate(row.id)}
              className="p-1.5 rounded hover:bg-green-50 text-gray-500 hover:text-green-600 transition-colors"
              aria-label="Ativar campanha"
              title="Ativar"
            >
              <Play className="w-4 h-4" />
            </button>
          )}

          {row.status === "ACTIVE" && (
            <>
              <button
                onClick={() => {
                  const url = `${window.location.origin}/survey/${row.survey_token}`;
                  void navigator.clipboard.writeText(url);
                  toast.success("Link copiado!");
                }}
                className="p-1.5 rounded hover:bg-blue-50 text-gray-500 hover:text-blue-600 transition-colors"
                aria-label="Copiar link da pesquisa"
                title="Copiar link"
              >
                <ExternalLink className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleClose(row.id)}
                className="p-1.5 rounded hover:bg-amber-50 text-gray-500 hover:text-amber-600 transition-colors"
                aria-label="Encerrar campanha"
                title="Encerrar"
              >
                <Square className="w-4 h-4" />
              </button>
            </>
          )}

          {(row.status === "DRAFT" || row.status === "ARCHIVED") && (
            <button
              onClick={() => setDeleteId(row.id)}
              className="p-1.5 rounded hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors"
              aria-label="Excluir campanha"
              title="Excluir"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
      className: "w-36",
    },
  ];

  const handleActivate = async (id: string) => {
    try {
      await activateMutation.mutateAsync(id);
      toast.success("Campanha ativada com sucesso!");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  const handleClose = async (id: string) => {
    try {
      await closeMutation.mutateAsync(id);
      toast.success("Campanha encerrada.");
    } catch (error) {
      toast.error(extractApiError(error).message);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success("Campanha excluída.");
    } catch (error) {
      toast.error(extractApiError(error).message);
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Campanhas"
        description="Gerencie suas campanhas de pesquisa NR-1"
        breadcrumbs={[{ label: "Campanhas" }]}
        actions={
          <button
            onClick={() => router.push(`${ROUTES.CAMPAIGNS}/new`)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors"
          >
            <Plus className="w-4 h-4" aria-hidden="true" />
            Nova Campanha
          </button>
        }
      />

      <DataTable
        data={data?.items ?? []}
        columns={columns}
        isLoading={isLoading}
        emptyTitle="Nenhuma campanha encontrada"
        emptyDescription="Crie sua primeira campanha para começar a coletar dados."
        page={pagination.page}
        pageSize={pagination.pageSize}
        total={data?.total ?? 0}
        onPageChange={pagination.setPage}
      />

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
        title="Excluir campanha"
        description="Esta ação não pode ser desfeita. A campanha e todos os dados associados serão removidos permanentemente."
        confirmLabel="Excluir"
        variant="destructive"
        onConfirm={handleDelete}
        isLoading={deleteMutation.isPending}
      />
    </>
  );
}
