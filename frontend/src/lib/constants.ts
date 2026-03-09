// API
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const API_VERSION = "/api/v1";
export const API_URL = `${API_BASE_URL}${API_VERSION}`;

// Pagination
export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

// Auth
export const ACCESS_TOKEN_KEY = "access_token";
export const SESSION_COOKIE_NAME = "session";

// Risk Levels (NR-1)
export const RISK_LEVELS = {
  CRITICAL: "CRITICAL",
  HIGH: "HIGH",
  MEDIUM: "MEDIUM",
  LOW: "LOW",
  MINIMAL: "MINIMAL",
} as const;

export type RiskLevel = (typeof RISK_LEVELS)[keyof typeof RISK_LEVELS];

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  CRITICAL: "Risco Crítico",
  HIGH: "Risco Alto",
  MEDIUM: "Risco Médio",
  LOW: "Risco Baixo",
  MINIMAL: "Risco Mínimo",
};

export const RISK_LEVEL_CLASSES: Record<RiskLevel, string> = {
  CRITICAL: "bg-red-50 text-red-700 border-red-200",
  HIGH: "bg-amber-50 text-amber-700 border-amber-200",
  MEDIUM: "bg-yellow-50 text-yellow-700 border-yellow-200",
  LOW: "bg-green-50 text-green-700 border-green-200",
  MINIMAL: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

// Campaign Status
export const CAMPAIGN_STATUS = {
  DRAFT: "DRAFT",
  ACTIVE: "ACTIVE",
  CLOSED: "CLOSED",
  ARCHIVED: "ARCHIVED",
} as const;

export type CampaignStatus = (typeof CAMPAIGN_STATUS)[keyof typeof CAMPAIGN_STATUS];

export const CAMPAIGN_STATUS_LABELS: Record<CampaignStatus, string> = {
  DRAFT: "Rascunho",
  ACTIVE: "Ativa",
  CLOSED: "Encerrada",
  ARCHIVED: "Arquivada",
};

// User Roles
export const USER_ROLES = {
  SUPER_ADMIN: "super_admin",
  ADMIN: "admin",
  HR_MANAGER: "hr_manager",
  EMPLOYEE: "employee",
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

// Routes
export const ROUTES = {
  LOGIN: "/login",
  RESET_PASSWORD: "/reset-password",
  DASHBOARD: "/dashboard",
  CAMPAIGNS: "/campaigns",
  REPORTS: "/reports",
  ACTION_PLANS: "/action-plans",
  AI_ANALYSIS: "/ai-analysis",
  WHISTLEBLOWER: "/whistleblower",
  STORAGE: "/storage",
  SETTINGS: "/settings",
  SUPER_ADMIN: "/super-admin",
} as const;

// Date formats
export const DATE_FORMAT = "dd/MM/yyyy";
export const DATETIME_FORMAT = "dd/MM/yyyy HH:mm";
export const DATE_FORMAT_ISO = "yyyy-MM-dd";

// HSE-IT Dimensions (NR-1 compliance)
export const HSE_IT_DIMENSIONS = [
  "Demandas do Trabalho",
  "Controle sobre o Trabalho",
  "Apoio Gerencial",
  "Apoio de Colegas",
  "Relacionamentos",
  "Papel Organizacional",
  "Mudança Organizacional",
] as const;

export type HseItDimension = (typeof HSE_IT_DIMENSIONS)[number];
