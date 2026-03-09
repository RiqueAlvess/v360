import { describe, it, expect } from "vitest";
import { decodeToken, isTokenExpired, isTokenExpiringSoon, getTokenRole } from "../auth";

// Helper to create a fake JWT with a payload
function createFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake_signature`;
}

describe("decodeToken", () => {
  it("decodes a valid token", () => {
    const payload = {
      sub: "user-123",
      email: "test@example.com",
      role: "admin",
      tenant_id: "tenant-456",
      exp: 9999999999,
      iat: 1000000000,
    };
    const token = createFakeJwt(payload);
    const decoded = decodeToken(token);
    expect(decoded).not.toBeNull();
    expect(decoded?.sub).toBe("user-123");
    expect(decoded?.role).toBe("admin");
  });

  it("returns null for invalid token format", () => {
    expect(decodeToken("not-a-jwt")).toBeNull();
    expect(decodeToken("")).toBeNull();
  });
});

describe("isTokenExpired", () => {
  it("returns true for an expired token", () => {
    const token = createFakeJwt({
      sub: "user-123",
      exp: 1000, // far in the past
      iat: 100,
      role: "admin",
      email: "x@x.com",
      tenant_id: "t1",
    });
    expect(isTokenExpired(token)).toBe(true);
  });

  it("returns false for a valid token", () => {
    const token = createFakeJwt({
      sub: "user-123",
      exp: 9999999999, // far in the future
      iat: 1000000000,
      role: "admin",
      email: "x@x.com",
      tenant_id: "t1",
    });
    expect(isTokenExpired(token)).toBe(false);
  });

  it("returns true for an invalid token", () => {
    expect(isTokenExpired("invalid")).toBe(true);
  });
});

describe("isTokenExpiringSoon", () => {
  it("returns true if token expires within threshold", () => {
    const now = Math.floor(Date.now() / 1000);
    const token = createFakeJwt({
      sub: "user-123",
      exp: now + 30, // expires in 30s
      iat: now - 100,
      role: "admin",
      email: "x@x.com",
      tenant_id: "t1",
    });
    expect(isTokenExpiringSoon(token, 60)).toBe(true);
  });

  it("returns false if token has plenty of time left", () => {
    const now = Math.floor(Date.now() / 1000);
    const token = createFakeJwt({
      sub: "user-123",
      exp: now + 3600, // expires in 1 hour
      iat: now - 100,
      role: "admin",
      email: "x@x.com",
      tenant_id: "t1",
    });
    expect(isTokenExpiringSoon(token, 60)).toBe(false);
  });
});

describe("getTokenRole", () => {
  it("returns the role from a valid token", () => {
    const token = createFakeJwt({
      sub: "user-123",
      exp: 9999999999,
      iat: 1000,
      role: "hr_manager",
      email: "x@x.com",
      tenant_id: "t1",
    });
    expect(getTokenRole(token)).toBe("hr_manager");
  });

  it("returns null for invalid token", () => {
    expect(getTokenRole("bad")).toBeNull();
  });
});
