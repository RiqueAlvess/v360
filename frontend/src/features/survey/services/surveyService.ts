import api from "@/lib/api";
import type { PublicSurvey, SurveySubmission } from "@/types";

// Public survey service — no auth required
export const surveyService = {
  async getSurvey(token: string): Promise<PublicSurvey> {
    const response = await api.get<PublicSurvey>(`/survey/${token}`);
    return response.data;
  },

  async submitSurvey(token: string, submission: SurveySubmission): Promise<{ protocol: string }> {
    const response = await api.post<{ protocol: string }>(`/survey/${token}/submit`, submission);
    return response.data;
  },
};
