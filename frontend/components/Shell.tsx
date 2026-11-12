"use client";

import type { AuthUser } from "@/lib/auth";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const NAV = [
  { href: "/", label: "Главная панель" },
  { href: "/shipments", label: "Грузы" },
  { href: "/map", label: "Карта перевозок" },
  { href: "/analytics", label: "ИИ-аналитика" },
  { href: "/routes", label: "Маршруты" },
  { href: "/customs", label: "Таможня и документы" },
  { href: "/ecology", label: "Экологическая аналитика" },
];

const EXTRA = [
  { href: "/notifications", label: "Уведомления" },
  { href: "/profile", label: "Профиль" },
  { href: "/logout", label: "Выход" },
];

export function Shell({ children, user }: { children: ReactNode; user: AuthUser | null }) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside style={{ width: 220, borderRight: "1px solid #ccc", padding: 12 }}>
        <p style={{ margin: "0 0 12px", fontWeight: "bold" }}>Smart Caspian Transit</p>
        {user && (
          <p className="muted" style={{ margin: "0 0 12px", fontSize: 12 }}>
            {user.name}
            <br />
            {user.role}
          </p>
        )}
        <nav style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className={isActive(item.href) ? "active" : ""}>
              {item.label}
            </Link>
          ))}
        </nav>
        <hr style={{ margin: "16px 0" }} />
        <nav style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {EXTRA.map((item) => (
            <Link key={item.href} href={item.href} className={isActive(item.href) ? "active" : ""}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main style={{ flex: 1, padding: 16 }}>{children}</main>
    </div>
  );
}
