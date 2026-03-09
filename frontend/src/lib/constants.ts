// API
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const API_VERSION = "/api/v1";
export const API_URL = `${API_BASE_URL}${API_VERSION}`;

// ─── Rotas da API ──────────────────────────────────────────────────────────────
// Centralização de todos os endpoints do backend. Referencie sempre estas
// constantes no lugar de strings hardcodadas ao fazer chamadas HTTP.
// Prefixo base: API_URL (ex.: `${API_URL}${API_ROUTES.AUTH.LOGIN}`)
// ───────────────────────────────────────────────────────────────────────────────
export const API_ROUTES = {

  // ── Autenticação (/auth) ──────────────────────────────────────────────────
  AUTH: {
    // Autentica o usuário com e-mail e senha, retorna access_token e refresh_token
    LOGIN: "/auth/login",
    // Rotaciona o refresh_token e emite um novo par de tokens
    REFRESH: "/auth/refresh",
    // Revoga o refresh_token encerrando a sessão
    LOGOUT: "/auth/logout",
    // Agenda limpeza interna de tokens expirados (uso interno/cron)
    SCHEDULE_TOKEN_CLEANUP: "/auth/admin/schedule-token-cleanup",
  },

  // ── Campanhas (/campaigns) ────────────────────────────────────────────────
  CAMPAIGNS: {
    // Cria uma nova campanha (já inicializa o checklist NR-1 automaticamente)
    CREATE: "/campaigns",
    // Lista campanhas da empresa com paginação
    LIST: "/campaigns",
    // Retorna os detalhes de uma campanha específica
    DETAIL: (campaignId: string) => `/campaigns/${campaignId}`,
  },

  // ── Respostas de Pesquisa (/survey-responses) ─────────────────────────────
  SURVEY_RESPONSES: {
    // Submete uma resposta anônima para a campanha indicada (sem autenticação)
    SUBMIT: (campaignId: string) => `/survey-responses/campaigns/${campaignId}`,
    // Lista respostas anonimizadas de uma campanha com paginação (requer auth)
    LIST: "/survey-responses",
  },

  // ── Checklist NR-1 (/checklists) ─────────────────────────────────────────
  CHECKLISTS: {
    // Lista itens do checklist NR-1 de uma campanha com progresso e paginação
    LIST: (campaignId: string) => `/checklists/${campaignId}`,
    // Alterna o status de conclusão (concluído/pendente) de um item
    TOGGLE_ITEM: (itemId: string) => `/checklists/items/${itemId}/toggle`,
    // Lista arquivos de evidência vinculados a um item do checklist
    LIST_EVIDENCIAS: (itemId: string) => `/checklists/items/${itemId}/evidencias`,
    // Registra metadados de um arquivo de evidência em um item
    CREATE_EVIDENCIA: (itemId: string) => `/checklists/items/${itemId}/evidencias`,
    // Remove (soft delete) um arquivo de evidência de um item
    DELETE_EVIDENCIA: (itemId: string, fileId: string) =>
      `/checklists/items/${itemId}/evidencias/${fileId}`,
    // Exporta o checklist completo de uma campanha (stub — Módulo 05)
    EXPORT: (campaignId: string) => `/checklists/${campaignId}/export`,
  },

  // ── Planos de Ação (/action-plans) ───────────────────────────────────────
  ACTION_PLANS: {
    // Lista planos de ação de uma campanha com paginação e filtros
    LIST: (campaignId: string) => `/action-plans/${campaignId}`,
    // Cria um novo plano de ação para a campanha (somente admin/gerente)
    CREATE: (campaignId: string) => `/action-plans/${campaignId}`,
    // Retorna detalhes de um plano de ação incluindo evidências
    DETAIL: (campaignId: string, planId: string) =>
      `/action-plans/${campaignId}/${planId}`,
    // Atualiza campos de um plano de ação (somente admin/gerente)
    UPDATE: (campaignId: string, planId: string) =>
      `/action-plans/${campaignId}/${planId}`,
    // Altera o status de um plano de ação (somente admin/gerente)
    UPDATE_STATUS: (campaignId: string, planId: string) =>
      `/action-plans/${campaignId}/${planId}/status`,
    // Cancela (soft delete) um plano de ação (somente admin/gerente)
    DELETE: (campaignId: string, planId: string) =>
      `/action-plans/${campaignId}/${planId}`,
    // Registra metadados de evidência em um plano de ação
    CREATE_EVIDENCIA: (campaignId: string, planId: string) =>
      `/action-plans/${campaignId}/${planId}/evidencias`,
  },

  // ── Dashboard (/dashboard) ────────────────────────────────────────────────
  DASHBOARD: {
    // Retorna o resumo geral, pontuações por dimensão e heatmap paginado
    SUMMARY: (campaignId: string) => `/dashboard/${campaignId}`,
    // Retorna o heatmap setor × dimensão com paginação e filtros opcionais
    HEATMAP: (campaignId: string) => `/dashboard/${campaignId}/heatmap`,
    // Lista as 5 combinações setor+dimensão com maior nível de risco
    TOP_RISKS: (campaignId: string) => `/dashboard/${campaignId}/top-risks`,
    // Compara até 3 campanhas por dimensão de análise
    COMPARE: "/dashboard/compare",
    // Série temporal de pontuações por campanha (tendências ao longo do tempo)
    TRENDS: (companyId: string) => `/dashboard/trends/${companyId}`,
  },

  // ── Análises de IA (/ai-analyses) ─────────────────────────────────────────
  AI_ANALYSES: {
    // Solicita uma nova análise de IA (enfileira tarefa; limite: 10/hora por empresa)
    REQUEST: "/ai-analyses/request",
    // Consulta status e resultado de uma análise (polling)
    DETAIL: (analysisId: string) => `/ai-analyses/${analysisId}`,
    // Lista análises com paginação e filtros por tipo e status
    LIST: "/ai-analyses",
    // Retorna um resumo agregado das análises concluídas de uma campanha
    SUMMARY: (campaignId: string) => `/ai-analyses/${campaignId}/summary`,
  },

  // ── Arquivos (/files) ─────────────────────────────────────────────────────
  FILES: {
    // Faz upload de um arquivo para o Cloudflare R2 (multipart/form-data, máx. 20 MB)
    UPLOAD: "/files/upload",
    // Gera URL assinada de download temporária para um arquivo
    SIGNED_URL: (fileId: string) => `/files/${fileId}/url`,
    // Lista arquivos por contexto e referência com paginação
    LIST: "/files",
    // Remove (soft delete) um arquivo pelo seu ID
    DELETE: (fileId: string) => `/files/${fileId}`,
  },

  // ── Canal de Denúncias — público (/denuncia) ──────────────────────────────
  WHISTLEBLOWER: {
    // Submete uma denúncia anônima para a empresa (sem auth; retorna token único)
    SUBMIT: (companySlug: string) => `/denuncia/${companySlug}/submit`,
    // Consulta status e resposta institucional via token de denúncia (público)
    CONSULT: (companySlug: string) => `/denuncia/${companySlug}/consulta`,
  },

  // ── Canal de Denúncias — admin (/admin/whistleblower) ────────────────────
  WHISTLEBLOWER_ADMIN: {
    // Lista denúncias recebidas com paginação e filtro por status
    LIST: "/admin/whistleblower",
    // Retorna os detalhes de uma denúncia específica
    DETAIL: (reportId: string) => `/admin/whistleblower/${reportId}`,
    // Registra a resposta institucional a uma denúncia (somente admin/gerente)
    RESPOND: (reportId: string) => `/admin/whistleblower/${reportId}/responder`,
  },

  // ── Notificações (/notifications) ─────────────────────────────────────────
  NOTIFICATIONS: {
    // Lista notificações do usuário autenticado com paginação e filtro de leitura
    LIST: "/notifications",
    // Retorna a contagem de notificações não lidas (badge)
    COUNT_UNREAD: "/notifications/count",
    // Marca uma notificação específica como lida
    MARK_READ: (notificationId: string) => `/notifications/${notificationId}/read`,
    // Marca todas as notificações do usuário como lidas
    MARK_ALL_READ: "/notifications/read-all",
    // Remove (soft delete) uma notificação específica
    DELETE: (notificationId: string) => `/notifications/${notificationId}`,
    // Remove (soft delete) todas as notificações já lidas
    CLEAR_ALL: "/notifications/clear-all",
  },

  // ── Webhooks (/webhooks) ──────────────────────────────────────────────────
  WEBHOOKS: {
    // Recebe eventos de status de entrega de e-mail do Resend (requer X-Webhook-Secret)
    EMAIL: "/webhooks/email",
  },
} as const;

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
