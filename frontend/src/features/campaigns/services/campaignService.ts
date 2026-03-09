import api from "@/lib/api";
import type { Campaign, CampaignCreate, CampaignUpdate, PaginatedResponse } from "@/types";
import type { PaginationParams } from "@/types";
import { buildQueryParams } from "@/lib/utils";

export interface CampaignFilters extends PaginationParams {
  status?: string;
  search?: string;
}

export const campaignService = {
  async list(filters: CampaignFilters = {}): Promise<PaginatedResponse<Campaign>> {
    const params = buildQueryParams(filters);
    const response = await api.get<PaginatedResponse<Campaign>>(`/campaigns${params}`);
    return response.data;
  },

  async getById(id: string): Promise<Campaign> {
    const response = await api.get<Campaign>(`/campaigns/${id}`);
    return response.data;
  },

  async create(data: CampaignCreate): Promise<Campaign> {
    const response = await api.post<Campaign>("/campaigns", data);
    return response.data;
  },

  async update(id: string, data: CampaignUpdate): Promise<Campaign> {
    const response = await api.patch<Campaign>(`/campaigns/${id}`, data);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/campaigns/${id}`);
  },

  async activate(id: string): Promise<Campaign> {
    const response = await api.post<Campaign>(`/campaigns/${id}/activate`);
    return response.data;
  },

  async close(id: string): Promise<Campaign> {
    const response = await api.post<Campaign>(`/campaigns/${id}/close`);
    return response.data;
  },

  async getSurveyUrl(id: string): Promise<{ url: string; token: string }> {
    const response = await api.get<{ url: string; token: string }>(`/campaigns/${id}/survey-url`);
    return response.data;
  },
};
