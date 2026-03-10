import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = [
  '/login',
  '/reset-password',
  '/survey',
  '/denuncia',
  '/whistleblower',
];

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_PATHS.some(path => pathname.startsWith(path));
  if (isPublic) return NextResponse.next();

  // Verifica apenas PRESENÇA do cookie — a validade real é verificada pelo backend
  const token = request.cookies.get("v360_access_token")?.value;

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|api/|.well-known|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
