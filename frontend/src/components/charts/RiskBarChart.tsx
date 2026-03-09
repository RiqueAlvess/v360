"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { RiskDistribution } from "@/types";
import { RISK_LEVEL_LABELS } from "@/lib/constants";

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "#C0392B",
  HIGH: "#E67E22",
  MEDIUM: "#F1C40F",
  LOW: "#27AE60",
  MINIMAL: "#0E9E6E",
};

interface RiskBarChartProps {
  data: RiskDistribution[];
  className?: string;
}

export function RiskBarChart({ data, className }: RiskBarChartProps) {
  const chartData = data.map((item) => ({
    ...item,
    label: RISK_LEVEL_LABELS[item.level],
    color: RISK_COLORS[item.level] || "#718096",
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#718096" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#718096" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number) => [`${value} pessoas`, "Quantidade"]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
