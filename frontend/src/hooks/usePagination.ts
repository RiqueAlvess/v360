"use client";

import { useState, useCallback } from "react";
import { DEFAULT_PAGE_SIZE } from "@/lib/constants";

export interface PaginationState {
  page: number;
  pageSize: number;
}

export interface UsePaginationReturn extends PaginationState {
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  reset: () => void;
  getQueryParams: () => { page: number; page_size: number };
}

export function usePagination(initialPageSize = DEFAULT_PAGE_SIZE): UsePaginationReturn {
  const [page, setPageState] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  const setPage = useCallback((newPage: number) => {
    setPageState(Math.max(1, newPage));
  }, []);

  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPageState(1); // Reset to first page when changing page size
  }, []);

  const nextPage = useCallback(() => {
    setPageState((p) => p + 1);
  }, []);

  const prevPage = useCallback(() => {
    setPageState((p) => Math.max(1, p - 1));
  }, []);

  const reset = useCallback(() => {
    setPageState(1);
    setPageSizeState(initialPageSize);
  }, [initialPageSize]);

  const getQueryParams = useCallback(
    () => ({ page, page_size: pageSize }),
    [page, pageSize]
  );

  return {
    page,
    pageSize,
    setPage,
    setPageSize,
    nextPage,
    prevPage,
    reset,
    getQueryParams,
  };
}
