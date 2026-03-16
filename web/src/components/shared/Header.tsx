"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  AUTH_STATE_CHANGE_EVENT,
  getUserInitials,
  readStoredAuthUser,
  type AuthUser,
} from "@/lib/auth";

const Header = () => {
  const pathname = usePathname();
  const [currentUser, setCurrentUser] = React.useState<AuthUser | null>(null);
  const navigationItems = [
    { label: "Home", href: "/" },
    { label: "Products", href: "/products" },
  ];

  React.useEffect(() => {
    const syncCurrentUser = () => {
      setCurrentUser(readStoredAuthUser());
    };

    syncCurrentUser();
    window.addEventListener("storage", syncCurrentUser);
    window.addEventListener(AUTH_STATE_CHANGE_EVENT, syncCurrentUser);

    return () => {
      window.removeEventListener("storage", syncCurrentUser);
      window.removeEventListener(AUTH_STATE_CHANGE_EVENT, syncCurrentUser);
    };
  }, []);

  return (
    <nav className="border-b bg-transparent backdrop-blur-md w-full md:sticky md:top-0 md:z-50">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-3 px-3 sm:h-16 sm:gap-6 sm:px-4 md:px-0">
        {/* 1. LOGO */}
        <Link href="/" className="flex items-center shrink-0">
          <span className="text-xl sm:text-2xl lg:text-3xl font-bold text-[#003d29]">
            Vibe
          </span>
        </Link>

        {/* 2. NAVIGATION MENU */}
        <div className="hidden md:flex items-center gap-5 lg:gap-8">
          {navigationItems.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm lg:text-base transition-colors duration-200 font-bold relative ${
                  isActive
                    ? "text-emerald-600"
                    : "text-gray-700 hover:text-emerald-600"
                }`}
              >
                {item.label}
                {isActive && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-600" />
                )}
              </Link>
            );
          })}
        </div>

        {/* SPACER */}
        <div className="flex-1" />

        {/* 3. CART & AUTH BUTTONS */}
        <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
          {/* CART BUTTON */}
          <Button
            asChild
            variant="ghost"
            size="icon"
            className="relative size-8 rounded-full hover:bg-gray-100 sm:size-10"
          >
            <Link href="/cart">
              <ShoppingCart className="size-4 text-gray-700 sm:size-5" />
              <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-semibold text-white sm:size-5 sm:text-xs">
                0
              </span>
            </Link>
          </Button>

          {currentUser ? (
            <Button
              type="button"
              variant="outline"
              className="flex h-9 items-center gap-2 rounded-full border-emerald-200 bg-white/70 px-3 text-sm font-medium text-[#003d29] shadow-sm backdrop-blur-sm hover:bg-white sm:h-10 sm:px-4"
            >
              <Avatar className="size-7 border border-emerald-200 sm:size-8">
                <AvatarFallback>{getUserInitials(currentUser)}</AvatarFallback>
              </Avatar>
              <span>Account</span>
            </Button>
          ) : (
            <Button
              asChild
              className="rounded-full bg-[#003d29] px-3 py-1.5 text-[11px] font-medium text-white hover:bg-[#002a1c] sm:px-6 sm:py-2 sm:text-sm"
            >
              <Link href="/auth">Sign In</Link>
            </Button>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Header;
