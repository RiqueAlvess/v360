"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Megaphone,
  FileBarChart,
  MessageSquareWarning,
  Brain,
  ClipboardList,
  HardDrive,
  Settings,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: ROUTES.DASHBOARD, icon: LayoutDashboard },
  { label: "Campanhas", href: ROUTES.CAMPAIGNS, icon: Megaphone },
  { label: "Relatórios", href: ROUTES.REPORTS, icon: FileBarChart },
  { label: "Canal de Denúncias", href: ROUTES.WHISTLEBLOWER, icon: MessageSquareWarning },
  { label: "Análise IA", href: ROUTES.AI_ANALYSIS, icon: Brain },
  { label: "Planos de Ação", href: ROUTES.ACTION_PLANS, icon: ClipboardList },
  { label: "Armazenamento", href: ROUTES.STORAGE, icon: HardDrive },
  { label: "Configurações", href: ROUTES.SETTINGS, icon: Settings },
];

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileNav({ isOpen, onClose }: MobileNavProps) {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const router = useRouter();

  // Close nav when route changes
  useEffect(() => {
    onClose();
  }, [pathname, onClose]);

  // Prevent body scroll when nav is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const handleLogout = async () => {
    await logout();
    router.push(ROUTES.LOGIN);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 lg:hidden"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 sidebar-bg flex flex-col lg:hidden",
          "transform transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Menu de navegação"
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-blue-900">
          <span className="text-white font-bold text-lg">VIVAMENTE 360°</span>
          <button
            onClick={onClose}
            className="p-2 rounded-md text-blue-200 hover:bg-blue-800 hover:text-white"
            aria-label="Fechar menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto" aria-label="Navegação mobile">
          <ul className="space-y-1 px-3">
            {navItems.map((item) => {
              const isActive =
                item.href === ROUTES.DASHBOARD
                  ? pathname === item.href
                  : pathname.startsWith(item.href);

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-3 py-3 rounded-md transition-colors",
                      "text-sm font-medium sidebar-text",
                      isActive
                        ? "bg-[var(--color-sidebar-active)] text-white"
                        : "hover:bg-blue-800 hover:text-white"
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <item.icon className="w-5 h-5" aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User section */}
        <div className="border-t border-blue-900 p-4">
          {user && (
            <div className="mb-3">
              <p className="text-sm text-white font-medium truncate">{user.full_name}</p>
              <p className="text-xs text-blue-300 truncate">{user.email}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-md text-sm font-medium text-blue-200 hover:bg-blue-800 hover:text-white transition-colors"
          >
            <LogOut className="w-5 h-5" aria-hidden="true" />
            <span>Sair</span>
          </button>
        </div>
      </div>
    </>
  );
}
