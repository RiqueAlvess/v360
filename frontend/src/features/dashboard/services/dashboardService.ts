import api from "@/lib/api";
import type { DashboardData } from "@/types";

export const dashboardService = {
  async getData(): Promise<DashboardData> {
    const response = await api.get<DashboardData>("/dashboard");
    return response.data;
  },
};
