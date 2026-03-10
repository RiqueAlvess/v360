/**
 * Generic paginated response from the backend
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Standard API error response
 */
export interface ApiErrorResponse {
  detail: string;
  message?: string;
  code?: string;
}

/**
 * Pagination query params
 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/**
 * Base entity fields
 */
export interface BaseEntity {
  id: string;
  created_at: string;
  updated_at: string;
}

/**
 * Auth types
 */
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at: string;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

/**
 * Tenant types
 */
export interface Tenant extends BaseEntity {
  name: string;
  cnpj: string;
  plan: string;
  is_active: boolean;
  settings: Record<string, unknown>;
}

/**
 * Campaign types
 */
export type CampaignStatus = "DRAFT" | "ACTIVE" | "CLOSED" | "ARCHIVED";

export interface Campaign extends BaseEntity {
  name: string;
  description: string | null;
  status: CampaignStatus;
  start_date: string;
  end_date: string;
  target_audience: string;
  anonymous_responses: boolean;
  reminder_days: number | null;
  tenant_id: string;
  survey_token: string;
  response_count: number;
  completion_rate: number;
}

export interface CampaignCreate {
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  target_audience: string;
  anonymous_responses: boolean;
  reminder_days?: number;
}

export interface CampaignUpdate extends Partial<CampaignCreate> {
  status?: CampaignStatus;
}

/**
 * Survey types (HSE-IT)
 */
export type QuestionType = "LIKERT_5" | "LIKERT_7" | "TEXT" | "MULTIPLE_CHOICE" | "YES_NO";

export interface SurveyQuestion {
  id: string;
  text: string;
  type: QuestionType;
  dimension: string;
  order: number;
  required: boolean;
  options?: string[];
}

export interface SurveyResponse {
  question_id: string;
  answer: string | number;
}

export interface SurveySubmission {
  token: string;
  responses: SurveyResponse[];
}

export interface PublicSurvey {
  campaign_name: string;
  company_name: string;
  questions: SurveyQuestion[];
  is_anonymous: boolean;
}

/**
 * Dashboard types
 */
export type RiskLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "MINIMAL";

export interface DashboardKpis {
  total_employees: number;
  total_campaigns: number;
  active_campaigns: number;
  avg_completion_rate: number;
  overall_risk_level: RiskLevel;
  risk_score: number;
  last_updated: string;
}

export interface HseItScore {
  dimension: string;
  score: number;
  risk_level: RiskLevel;
  benchmark: number;
}

export interface DashboardData {
  kpis: DashboardKpis;
  hse_scores: HseItScore[];
  response_trend: TrendPoint[];
  risk_distribution: RiskDistribution[];
}

export interface TrendPoint {
  date: string;
  responses: number;
  completion_rate: number;
}

export interface RiskDistribution {
  level: RiskLevel;
  count: number;
  percentage: number;
}

/**
 * Report types
 */
export type ReportFormat = "PDF" | "DOCX" | "XLSX";

export interface Report extends BaseEntity {
  name: string;
  format: ReportFormat;
  campaign_id: string | null;
  campaign_name: string | null;
  status: "PENDING" | "GENERATING" | "READY" | "FAILED";
  download_url: string | null;
  generated_at: string | null;
}

export interface ReportRequest {
  campaign_id?: string;
  format: ReportFormat;
  include_sections: string[];
}

/**
 * Action Plan types
 */
export type ActionPlanStatus = "PENDING" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type ActionPlanPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface ActionPlan extends BaseEntity {
  title: string;
  description: string;
  responsible_id: string;
  responsible_name: string;
  due_date: string;
  priority: ActionPlanPriority;
  status: ActionPlanStatus;
  campaign_id: string | null;
  risk_dimension: string | null;
  completed_at: string | null;
}

/**
 * Whistleblower types
 */
export type WhistleblowerStatus = "RECEIVED" | "IN_REVIEW" | "RESOLVED" | "DISMISSED";

export interface WhistleblowerReport extends BaseEntity {
  protocol: string;
  category: string;
  description: string;
  status: WhistleblowerStatus;
  is_anonymous: boolean;
  resolved_at: string | null;
}

export interface WhistleblowerCreate {
  category: string;
  description: string;
  is_anonymous: boolean;
  contact_email?: string;
}

/**
 * Storage types
 */
export interface StorageFile extends BaseEntity {
  name: string;
  original_name: string;
  size: number;
  content_type: string;
  bucket_key: string;
  uploaded_by_id: string;
  uploaded_by_name: string;
}

export interface SignedUrlResponse {
  url: string;
  expires_at: string;
}

/**
 * AI Analysis types
 */
export interface AiAnalysis extends BaseEntity {
  campaign_id: string;
  campaign_name: string;
  model: string;
  analysis_type: string;
  summary: string;
  key_findings: string[];
  recommendations: string[];
  risk_areas: AiRiskArea[];
  generated_at: string;
}

export interface AiRiskArea {
  dimension: string;
  risk_level: RiskLevel;
  description: string;
  affected_percentage: number;
}

/**
 * Super Admin types
 */
export interface TenantAdmin extends Tenant {
  user_count: number;
  campaign_count: number;
  last_activity: string | null;
}

export interface SystemStats {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  total_campaigns: number;
  total_responses: number;
}
