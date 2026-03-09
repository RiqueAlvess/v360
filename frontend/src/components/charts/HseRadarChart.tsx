"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { HseItScore } from "@/types";

interface HseRadarChartProps {
  data: HseItScore[];
  className?: string;
}

interface RadarDataPoint {
  dimension: string;
  score: number;
  benchmark: number;
}

const DIMENSION_SHORT_LABELS: Record<string, string> = {
  "Demandas do Trabalho": "Demandas",
  "Controle sobre o Trabalho": "Controle",
  "Apoio Gerencial": "Apoio Ger.",
  "Apoio de Colegas": "Apoio Col.",
  Relacionamentos: "Relac.",
  "Papel Organizacional": "Papel",
  "Mudança Organizacional": "Mudança",
};

export function HseRadarChart({ data, className }: HseRadarChartProps) {
  const chartData: RadarDataPoint[] = data.map((item) => ({
    dimension: DIMENSION_SHORT_LABELS[item.dimension] || item.dimension,
    score: Math.round(item.score),
    benchmark: Math.round(item.benchmark),
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={chartData}>
          <PolarGrid stroke="#E2E8F0" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 11, fill: "#718096" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "#A0AEC0" }}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#1A56A0"
            fill="#1A56A0"
            fillOpacity={0.25}
            strokeWidth={2}
          />
          <Radar
            name="Benchmark"
            dataKey="benchmark"
            stroke="#0E9E6E"
            fill="#0E9E6E"
            fillOpacity={0.1}
            strokeWidth={1.5}
            strokeDasharray="4 4"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number, name: string) => [
              `${value}%`,
              name === "score" ? "Score" : "Benchmark",
            ]}
          />
        </RadarChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 mt-2 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-primary" />
          <span>Score atual</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-green-500 border-dashed" style={{ borderTop: "2px dashed" }} />
          <span>Benchmark</span>
        </div>
      </div>
    </div>
  );
}
