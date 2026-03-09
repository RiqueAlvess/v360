import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/types";
import { RISK_LEVEL_LABELS, RISK_LEVEL_CLASSES, CAMPAIGN_STATUS_LABELS } from "@/lib/constants";
import type { CampaignStatus } from "@/lib/constants";

interface RiskBadgeProps {
  level: RiskLevel;
  className?: string;
}

export function RiskBadge({ level, className }: RiskBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        RISK_LEVEL_CLASSES[level],
        className
      )}
      role="status"
      aria-label={`Nível de risco: ${RISK_LEVEL_LABELS[level]}`}
    >
      {RISK_LEVEL_LABELS[level]}
    </span>
  );
}

const CAMPAIGN_STATUS_CLASSES: Record<CampaignStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700 border-gray-200",
  ACTIVE: "bg-green-50 text-green-700 border-green-200",
  CLOSED: "bg-blue-50 text-blue-700 border-blue-200",
  ARCHIVED: "bg-gray-50 text-gray-500 border-gray-200",
};

interface CampaignStatusBadgeProps {
  status: CampaignStatus;
  className?: string;
}

export function CampaignStatusBadge({ status, className }: CampaignStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        CAMPAIGN_STATUS_CLASSES[status],
        className
      )}
      role="status"
    >
      {CAMPAIGN_STATUS_LABELS[status]}
    </span>
  );
}

type GenericStatus = "success" | "warning" | "error" | "info" | "neutral";

const GENERIC_STATUS_CLASSES: Record<GenericStatus, string> = {
  success: "bg-green-50 text-green-700 border-green-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  error: "bg-red-50 text-red-700 border-red-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
  neutral: "bg-gray-100 text-gray-700 border-gray-200",
};

interface StatusBadgeProps {
  label: string;
  variant?: GenericStatus;
  className?: string;
}

export function StatusBadge({ label, variant = "neutral", className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        GENERIC_STATUS_CLASSES[variant],
        className
      )}
    >
      {label}
    </span>
  );
}
