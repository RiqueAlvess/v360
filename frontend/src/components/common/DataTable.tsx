"use client";

import { cn } from "@/lib/utils";
import { LoadingSpinner } from "./LoadingSpinner";
import { EmptyState } from "./EmptyState";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DEFAULT_PAGE_SIZE } from "@/lib/constants";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  // Pagination (FE-R6: mandatory for all lists)
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
  className?: string;
}

export function DataTable<T extends { id: string }>({
  data,
  columns,
  isLoading = false,
  emptyTitle = "Nenhum item encontrado",
  emptyDescription,
  page = 1,
  pageSize = DEFAULT_PAGE_SIZE,
  total = 0,
  onPageChange,
  className,
}: DataTableProps<T>) {
  const totalPages = Math.ceil(total / pageSize);
  const hasPrev = page > 1;
  const hasNext = page < totalPages;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide",
                    col.className
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="py-16">
                  <LoadingSpinner className="mx-auto" />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>
                  <EmptyState title={emptyTitle} description={emptyDescription} />
                </td>
              </tr>
            ) : (
              data.map((row, rowIndex) => (
                <tr
                  key={row.id}
                  className={cn(
                    "border-b border-gray-100 hover:bg-gray-50 transition-colors",
                    rowIndex === data.length - 1 && "border-b-0"
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn("px-4 py-3 text-gray-700", col.className)}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {onPageChange && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            {total > 0
              ? `Mostrando ${start}–${end} de ${total} itens`
              : "Nenhum item"}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={!hasPrev}
              className={cn(
                "p-1.5 rounded-md border transition-colors",
                hasPrev
                  ? "border-gray-300 hover:bg-gray-100 text-gray-700"
                  : "border-gray-200 text-gray-300 cursor-not-allowed"
              )}
              aria-label="Página anterior"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={!hasNext}
              className={cn(
                "p-1.5 rounded-md border transition-colors",
                hasNext
                  ? "border-gray-300 hover:bg-gray-100 text-gray-700"
                  : "border-gray-200 text-gray-300 cursor-not-allowed"
              )}
              aria-label="Próxima página"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
