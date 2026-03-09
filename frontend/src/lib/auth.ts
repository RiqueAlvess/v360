export interface JWTPayload {
  sub: string;
  email: string;
  role: string;
  tenant_id: string;
  exp: number;
  iat: number;
}

/**
 * Decode a JWT token without verifying the signature.
 * Signature verification happens server-side via middleware.
 */
export function decodeToken(token: string): JWTPayload | null {
  try {
    // jose's decodeJwt returns the payload
    const payload = decodeJwtPayload(token);
    return payload as JWTPayload;
  } catch {
    return null;
  }
}

/**
 * Decode JWT payload from base64 without verification (client-side only)
 */
function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT format");
  }
  const payload = parts[1];
  // Add padding if needed
  const padded = payload + "=".repeat((4 - (payload.length % 4)) % 4);
  const decoded = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(decoded) as Record<string, unknown>;
}

/**
 * Check if a JWT token is expired
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp < now;
}

/**
 * Check if a token expires within the next N seconds
 */
export function isTokenExpiringSoon(token: string, thresholdSeconds = 60): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp - now < thresholdSeconds;
}

/**
 * Get the role from a JWT token
 */
export function getTokenRole(token: string): string | null {
  const payload = decodeToken(token);
  return payload?.role ?? null;
}

/**
 * Get the user ID (sub) from a JWT token
 */
export function getTokenUserId(token: string): string | null {
  const payload = decodeToken(token);
  return payload?.sub ?? null;
}
