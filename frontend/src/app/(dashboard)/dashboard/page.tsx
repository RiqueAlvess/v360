"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { PageLoader } from "@/components/common/LoadingSpinner";
import { DashboardContent } from "@/features/dashboard/components/DashboardContent";
import { BarChart3 } from "lucide-react";
import type { PaginatedResponse, Campaign } from "@/types";
import Link from "next/link";

export default function DashboardPage() {
  // Step 1: fetch most recent campaign
  const { data: campaignsData, isLoading: loadingCampaigns } = useQuery({
    queryKey: ["campaigns", "latest"],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Campaign>>(
        "/campaigns?page=1&page_size=1"
      );
      return data;
    },
  });

  const latestCampaign = campaignsData?.items?.[0] ?? null;

  // Step 2: fetch dashboard only if a campaign exists
  const { data: dashboardData, isLoading: loadingDashboard } = useQuery({
    queryKey: ["dashboard", latestCampaign?.id],
    queryFn: async () => {
      const { data } = await api.get(`/dashboard/${latestCampaign!.id}`);
      return data;
    },
    enabled: !!latestCampaign,
  });

  const isLoading = loadingCampaigns || (!!latestCampaign && loadingDashboard);

  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Visão geral dos riscos psicossociais da sua empresa"
        breadcrumbs={[{ label: "Dashboard" }]}
      />

      {!latestCampaign ? (
        <div className="bg-white rounded-xl border border-gray-200">
          <EmptyState
            title="Nenhuma campanha ainda"
            description="Crie sua primeira campanha de avaliação psicossocial para ver os resultados aqui."
            icon={BarChart3}
            action={
              <Link
                href="/campaigns/new"
                className="inline-flex items-center px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Criar primeira campanha
              </Link>
            }
          />
        </div>
      ) : (
        <DashboardContent
          campaignId={latestCampaign.id}
          campaignName={latestCampaign.name}
          dashboardData={dashboardData}
        />
      )}
    </div>
  );
}
