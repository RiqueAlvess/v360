"use client";

import { Menu } from "lucide-react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { getInitials } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface HeaderProps {
  onMenuClick?: () => void;
  className?: string;
}

export function Header({ onMenuClick, className }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header
      className={cn(
        "flex items-center justify-between h-16 px-4 md:px-6",
        "bg-white border-b border-gray-200 flex-shrink-0",
        className
      )}
    >
      {/* Left side: mobile menu button */}
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="p-2 rounded-md text-gray-500 hover:bg-gray-100 lg:hidden"
            aria-label="Abrir menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        {/* Logo for mobile */}
        <span className="font-bold text-primary lg:hidden">VIVAMENTE 360°</span>
      </div>

      {/* Right side: user */}
      <div className="flex items-center gap-3">
        {/* User avatar */}
        {user && (
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center",
                "bg-primary text-white text-xs font-semibold"
              )}
              aria-label={`Usuário: ${user.full_name}`}
            >
              {getInitials(user.full_name)}
            </div>
            <div className="hidden md:block">
              <p className="text-sm font-medium text-gray-800 leading-tight">{user.full_name}</p>
              <p className="text-xs text-gray-500 leading-tight">{user.email}</p>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
