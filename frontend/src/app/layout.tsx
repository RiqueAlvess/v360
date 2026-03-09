import type { Metadata } from "next";
import { Providers } from "./providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: {
    default: "VIVAMENTE 360°",
    template: "%s | VIVAMENTE 360°",
  },
  description:
    "Plataforma SaaS B2B para gestão de riscos psicossociais no trabalho, em conformidade com a NR-1.",
  robots: {
    index: false, // B2B SaaS — não indexar
    follow: false,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
