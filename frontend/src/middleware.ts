import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || "change-this-secret-in-production"
);

interface JWTPayload {
  sub: string;
  email: string;
  role: string;
  tenant_id: string;
  exp: number;
}

async function verifyToken(token: string): Promise<JWTPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    return payload as unknown as JWTPayload;
  } catch {
    return null;
  }
}

// Rotas que NÃO precisam de autenticação
const PUBLIC_PATHS = [
  '/login',
  '/reset-password',
  '/survey',     // pesquisas públicas
  '/denuncia',   // canal de denúncias
  '/whistleblower',
  '/api/v1/auth/login',
  '/api/v1/auth/refresh',
];

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl;

  // Ignora rotas públicas
  const isPublic = PUBLIC_PATHS.some(path => pathname.startsWith(path));
  if (isPublic) return NextResponse.next();

  // Verifica token no header ou cookie
  // NOTA: o Next.js middleware NÃO acessa localStorage!
  // O token deve estar em cookie HttpOnly OU ser verificado client-side
  let token: string | null = null;

  const authHeader = request.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    token = authHeader.slice(7);
  } else {
    token = request.cookies.get("v360_access_token")?.value ?? null;
  }

  const payload = token ? await verifyToken(token) : null;
  const isAuthenticated = payload !== null;

  if (!isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Super admin routes — require super_admin role
  if (pathname.startsWith("/super-admin")) {
    if (payload.role !== "super_admin") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Protege apenas rotas da aplicação — exclui tudo que não é página
    '/((?!_next/static|_next/image|favicon.ico|api/|.well-known|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
