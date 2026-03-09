"use client";

import { useQuery } from "@tanstack/react-query";
import { dashboardService } from "../services/dashboardService";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardService.getData,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
