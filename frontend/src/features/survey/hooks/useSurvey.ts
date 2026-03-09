"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { surveyService } from "../services/surveyService";
import type { SurveySubmission } from "@/types";

export function useSurvey(token: string) {
  return useQuery({
    queryKey: ["survey", token],
    queryFn: () => surveyService.getSurvey(token),
    enabled: !!token,
    staleTime: Infinity, // Survey questions don't change
    retry: false,
  });
}

export function useSubmitSurvey(token: string) {
  return useMutation({
    mutationFn: (submission: SurveySubmission) =>
      surveyService.submitSurvey(token, submission),
  });
}
