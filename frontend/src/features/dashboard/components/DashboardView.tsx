"use client";

import { useDashboard } from "../hooks/useDashboard";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskBadge } from "@/components/common/StatusBadge";
import { HseRadarChart } from "@/components/charts/HseRadarChart";
import { RiskBarChart } from "@/components/charts/RiskBarChart";
import { TrendLineChart } from "@/components/charts/TrendLineChart";
import { PageLoader } from "@/components/common/LoadingSpinner";
import { formatNumber, formatPercent } from "@/lib/utils";
import { Users, Megaphone, TrendingUp, AlertTriangle } from "lucide-react";

export function DashboardView() {
  const { data, isLoading, error } = useDashboard();

  if (isLoading) return <PageLoader />;

  if (error || !data) {
    return (
      <div className="text-center py-16 text-gray-500">
        Erro ao carregar dados do dashboard.
      </div>
    );
  }

  const { kpis, hse_scores, response_trend, risk_distribution } = data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard NR-1"
        description="Visão geral dos riscos psicossociais da organização"
        breadcrumbs={[{ label: "Dashboard" }]}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          title="Total de Colaboradores"
          value={formatNumber(kpis.total_employees)}
          icon={Users}
          color="blue"
        />
        <KpiCard
          title="Campanhas Ativas"
          value={`${kpis.active_campaigns} / ${kpis.total_campaigns}`}
          icon={Megaphone}
          color="green"
        />
        <KpiCard
          title="Taxa Média de Resposta"
          value={formatPercent(kpis.avg_completion_rate)}
          icon={TrendingUp}
          color="purple"
        />
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 rounded-lg bg-amber-50">
              <AlertTriangle className="w-5 h-5 text-amber-600" aria-hidden="true" />
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-1">Risco Geral (NR-1)</p>
          <RiskBadge level={kpis.overall_risk_level} />
          <p className="text-xs text-gray-400 mt-1">Score: {Math.round(kpis.risk_score)}/100</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* HSE-IT Radar */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-base font-semibold text-gray-900 mb-4">
            Dimensões HSE-IT
          </h3>
          {hse_scores.length > 0 ? (
            <HseRadarChart data={hse_scores} />
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
              Dados insuficientes
            </div>
          )}
        </div>

        {/* Risk Distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-base font-semibold text-gray-900 mb-4">
            Distribuição de Riscos
          </h3>
          {risk_distribution.length > 0 ? (
            <RiskBarChart data={risk_distribution} />
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
              Dados insuficientes
            </div>
          )}
        </div>
      </div>

      {/* Trend Line */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-base font-semibold text-gray-900 mb-4">
          Tendência de Respostas (últimos 30 dias)
        </h3>
        {response_trend.length > 0 ? (
          <TrendLineChart data={response_trend} />
        ) : (
          <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
            Sem dados de tendência disponíveis
          </div>
        )}
      </div>
    </div>
  );
}

interface KpiCardProps {
  title: string;
  value: string;
  icon: React.ElementType;
  color: "blue" | "green" | "purple" | "amber";
}

const COLOR_CLASSES: Record<KpiCardProps["color"], string> = {
  blue: "bg-blue-50 text-blue-600",
  green: "bg-green-50 text-green-600",
  purple: "bg-purple-50 text-purple-600",
  amber: "bg-amber-50 text-amber-600",
};

function KpiCard({ title, value, icon: Icon, color }: KpiCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className={`p-2 rounded-lg ${COLOR_CLASSES[color]}`}>
          <Icon className="w-5 h-5" aria-hidden="true" />
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-1">{title}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
