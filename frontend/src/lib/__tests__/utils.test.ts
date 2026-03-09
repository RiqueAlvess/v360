import { describe, it, expect } from "vitest";
import {
  cn,
  formatDate,
  formatPercent,
  formatNumber,
  getInitials,
  truncate,
  isDefined,
  formatFileSize,
  buildQueryParams,
} from "../utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("handles conditional classes", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });

  it("resolves Tailwind conflicts", () => {
    expect(cn("p-4", "p-6")).toBe("p-6");
  });
});

describe("formatDate", () => {
  it("formats a valid date string", () => {
    const result = formatDate("2024-01-15");
    expect(result).toBe("15/01/2024");
  });

  it("returns dash for null", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("returns dash for undefined", () => {
    expect(formatDate(undefined)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("formats percentage correctly", () => {
    expect(formatPercent(75)).toContain("75");
  });

  it("formats zero percent", () => {
    expect(formatPercent(0)).toContain("0");
  });
});

describe("formatNumber", () => {
  it("formats a number with Brazilian locale", () => {
    const result = formatNumber(1000);
    expect(result).toContain("1");
  });
});

describe("getInitials", () => {
  it("returns initials from full name", () => {
    expect(getInitials("João Silva")).toBe("JS");
  });

  it("returns single initial for single name", () => {
    expect(getInitials("João")).toBe("J");
  });

  it("returns only first two initials", () => {
    expect(getInitials("João da Silva Santos")).toBe("JD");
  });
});

describe("truncate", () => {
  it("does not truncate short text", () => {
    expect(truncate("Hello", 10)).toBe("Hello");
  });

  it("truncates long text with ellipsis", () => {
    expect(truncate("Hello World", 8)).toBe("Hello Wo...");
  });
});

describe("isDefined", () => {
  it("returns true for defined values", () => {
    expect(isDefined("value")).toBe(true);
    expect(isDefined(0)).toBe(true);
    expect(isDefined(false)).toBe(true);
  });

  it("returns false for null and undefined", () => {
    expect(isDefined(null)).toBe(false);
    expect(isDefined(undefined)).toBe(false);
  });
});

describe("formatFileSize", () => {
  it("formats bytes", () => {
    expect(formatFileSize(0)).toBe("0 Bytes");
    expect(formatFileSize(500)).toBe("500 Bytes");
  });

  it("formats kilobytes", () => {
    expect(formatFileSize(1024)).toBe("1 KB");
  });

  it("formats megabytes", () => {
    expect(formatFileSize(1024 * 1024)).toBe("1 MB");
  });
});

describe("buildQueryParams", () => {
  it("builds query string from object", () => {
    const result = buildQueryParams({ page: 1, page_size: 20 });
    expect(result).toBe("?page=1&page_size=20");
  });

  it("filters out undefined values", () => {
    const result = buildQueryParams({ page: 1, status: undefined });
    expect(result).toBe("?page=1");
  });

  it("returns empty string for empty object", () => {
    expect(buildQueryParams({})).toBe("");
  });
});
