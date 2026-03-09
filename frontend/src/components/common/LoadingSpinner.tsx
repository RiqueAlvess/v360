import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeClasses = {
  sm: "w-4 h-4 border-2",
  md: "w-8 h-8 border-2",
  lg: "w-12 h-12 border-3",
};

export function LoadingSpinner({ size = "md", className, label = "Carregando..." }: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      className={cn("flex items-center justify-center", className)}
      aria-label={label}
    >
      <div
        className={cn(
          "animate-spin rounded-full border-gray-200 border-t-primary",
          sizeClasses[size]
        )}
        aria-hidden="true"
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-64">
      <LoadingSpinner size="lg" />
    </div>
  );
}
