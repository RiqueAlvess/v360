"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import type { TrendPoint } from "@/types";

interface TrendLineChartProps {
  data: TrendPoint[];
  className?: string;
}

export function TrendLineChart({ data, className }: TrendLineChartProps) {
  const chartData = data.map((point) => ({
    ...point,
    date: format(parseISO(point.date), "dd/MM", { locale: ptBR }),
    completionPct: Math.round(point.completion_rate),
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "#718096" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 11, fill: "#718096" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: "#718096" }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: "8px",
              fontSize: "12px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="responses"
            stroke="#1A56A0"
            strokeWidth={2}
            dot={false}
            name="Respostas"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="completionPct"
            stroke="#0E9E6E"
            strokeWidth={2}
            dot={false}
            name="Taxa de Conclusão (%)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
