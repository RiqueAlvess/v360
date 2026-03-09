"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";
import {
  LayoutDashboard,
  Megaphone,
  FileBarChart,
  MessageSquareWarning,
  Brain,
  ClipboardList,
  HardDrive,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useRouter } from "next/navigation";

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

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { logout, user } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push(ROUTES.LOGIN);
  };

  return (
    <aside
      className={cn(
        "flex flex-col h-full transition-all duration-300 ease-in-out",
        "sidebar-bg border-r border-blue-900",
        collapsed ? "w-16" : "w-64",
        className
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex items-center h-16 px-4 border-b border-blue-900",
          collapsed ? "justify-center" : "justify-between"
        )}
      >
        {!collapsed && (
          <span className="text-white font-bold text-lg tracking-tight">VIVAMENTE 360°</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md text-blue-200 hover:bg-blue-800 hover:text-white transition-colors"
          aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto" aria-label="Navegação principal">
        <ul className="space-y-1 px-2">
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
                    "flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors",
                    "text-sm font-medium sidebar-text",
                    isActive
                      ? "bg-[var(--color-sidebar-active)] text-white"
                      : "hover:bg-blue-800 hover:text-white",
                    collapsed && "justify-center px-2"
                  )}
                  aria-current={isActive ? "page" : undefined}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User section */}
      <div className="border-t border-blue-900 p-3">
        {!collapsed && user && (
          <div className="px-2 py-1 mb-2">
            <p className="text-xs text-blue-300 truncate">{user.full_name}</p>
            <p className="text-xs text-blue-400 truncate">{user.email}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className={cn(
            "flex items-center gap-3 w-full px-3 py-2 rounded-md",
            "text-sm font-medium text-blue-200 hover:bg-blue-800 hover:text-white transition-colors",
            collapsed && "justify-center px-2"
          )}
          aria-label="Sair"
          title={collapsed ? "Sair" : undefined}
        >
          <LogOut className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
          {!collapsed && <span>Sair</span>}
        </button>
      </div>
    </aside>
  );
}
