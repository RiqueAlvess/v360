"use client";

import { RiskBadge } from "@/components/common/StatusBadge";
import { HseRadarChart } from "@/components/charts/HseRadarChart";
import { formatNumber } from "@/lib/utils";
import { RISK_LEVEL_LABELS } from "@/lib/constants";
import { Users, BarChart3, AlertTriangle } from "lucide-react";
import type { RiskLevel, HseItScore } from "@/types";

interface CampaignDashboardData {
  total_respostas: number;
  indice_geral: number;
  nivel_geral: RiskLevel;
  hse_scores: HseItScore[];
}

interface DashboardContentProps {
  campaignId: string;
  campaignName: string;
  dashboardData: CampaignDashboardData | undefined;
}

export function DashboardContent({
  campaignName,
  dashboardData,
}: DashboardContentProps) {
  if (!dashboardData) {
    return (
      <div className="text-center py-16 text-gray-500">
        Erro ao carregar dados do dashboard.
      </div>
    );
  }

  const { total_respostas, indice_geral, nivel_geral, hse_scores } =
    dashboardData;

  const semRespostas = total_respostas === 0;

  return (
    <div className="space-y-6">
      {/* Campaign name subtitle */}
      <p className="text-sm text-gray-500">
        Campanha mais recente:{" "}
        <span className="font-medium text-gray-700">{campaignName}</span>
      </p>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 rounded-lg bg-blue-50">
              <Users className="w-5 h-5 text-blue-600" aria-hidden="true" />
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-1">Total de Respostas</p>
          <p className="text-2xl font-bold text-gray-900">
            {formatNumber(total_respostas)}
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 rounded-lg bg-purple-50">
              <BarChart3
                className="w-5 h-5 text-purple-600"
                aria-hidden="true"
              />
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-1">Índice Geral</p>
          <p className="text-2xl font-bold text-gray-900">
            {Math.round(indice_geral)}/100
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 rounded-lg bg-amber-50">
              <AlertTriangle
                className="w-5 h-5 text-amber-600"
                aria-hidden="true"
              />
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-1">Nível de Risco Geral</p>
          <RiskBadge level={nivel_geral} />
        </div>
      </div>

      {semRespostas ? (
        /* Waiting for responses */
        <div className="bg-white rounded-xl border border-gray-200 flex items-center justify-center py-16">
          <div className="text-center">
            <BarChart3
              className="w-12 h-12 text-gray-300 mx-auto mb-3"
              aria-hidden="true"
            />
            <p className="text-base font-semibold text-gray-700">
              Aguardando respostas
            </p>
            <p className="text-sm text-gray-500 mt-1 max-w-sm">
              Os resultados aparecerão aqui assim que os colaboradores
              responderem a pesquisa.
            </p>
          </div>
        </div>
      ) : (
        /* HSE-IT dimensions */
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
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

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-4">
              Pontuação por Dimensão
            </h3>
            <div className="space-y-3">
              {hse_scores.map((item) => (
                <div
                  key={item.dimension}
                  className="flex items-center justify-between gap-4"
                >
                  <span className="text-sm text-gray-700 min-w-0 truncate">
                    {item.dimension}
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${Math.min(item.score, 100)}%` }}
                        aria-hidden="true"
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-8 text-right">
                      {Math.round(item.score)}
                    </span>
                    <RiskBadge level={item.risk_level} />
                  </div>
                </div>
              ))}
              {hse_scores.length === 0 && (
                <p className="text-sm text-gray-400">
                  Nenhuma dimensão disponível.
                </p>
              )}
            </div>
            {hse_scores.length > 0 && (
              <p className="text-xs text-gray-400 mt-4">
                Níveis:{" "}
                {(
                  ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"] as RiskLevel[]
                ).map((lvl) => RISK_LEVEL_LABELS[lvl]).join(" · ")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
