"use client";

import type { AuthUser } from "@/lib/auth";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";
import styles from "./Shell.module.css";

const NAV = [
  { href: "/", label: "Главная панель", icon: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z" },
  { href: "/shipments", label: "Грузы", icon: "M12 22 3 17V7l9-5 9 5v10z M3 7l9 5 9-5 M12 12v10 M7.5 4.5l9 5" },
  { href: "/map", label: "Карта перевозок", icon: "m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z M9 3v15 M15 6v15" },
  { href: "/analytics", label: "AI-прогнозирование", icon: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M5 15v6 M2 18h6 M19 2v4 M17 4h4" },
  { href: "/routes", label: "Маршруты", icon: "M7 6h10a3.5 3.5 0 0 1 0 7h-9a3 3 0 0 0 0 6h9 M7 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0z M21 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0z" },
  { href: "/customs", label: "Таможня и документы", icon: "M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6" },
  { href: "/ecology", label: "Экологическая аналитика", icon: "M20 4c-7 0-13 2-13 8a5 5 0 0 0 5 5c6 0 8-6 8-13z M4 21l10-10" },
];

const EXTRA = [
  { href: "/notifications", label: "Уведомления", icon: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4" },
  { href: "/profile", label: "Профиль", icon: "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z M4 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2" },
  { href: "/logout", label: "Выход", icon: "M11 4H4v16h7 M9 12h11 M16 8l4 4-4 4" },
];

const mobileQuery = "(max-width: 760px)";
function subscribeToViewport(onChange: () => void) {
  const media = window.matchMedia(mobileQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}
const isMobileViewport = () => window.matchMedia(mobileQuery).matches;
const serverViewport = () => false;

function Icon({ path }: { path: string }) {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

export function Shell({ children, user }: { children: ReactNode; user: AuthUser | null }) {
  const pathname = usePathname();
  const mobile = useSyncExternalStore(subscribeToViewport, isMobileViewport, serverViewport);
  const [desktopExpanded, setDesktopExpanded] = useState(true);
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const expanded = mobile ? mobileExpanded : desktopExpanded;
  const overlay = mobile && mobileExpanded;

  useEffect(() => {
    if (!expanded) return;

    function onEscape(event: KeyboardEvent) {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (!mobile && !toggle.current?.closest("aside")?.contains(document.activeElement)) return;
      if (mobile) setMobileExpanded(false);
      else setDesktopExpanded(false);
      toggle.current?.focus();
    }

    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [expanded, mobile]);

  function closeAfterNavigation(event: MouseEvent<HTMLAnchorElement>) {
    if (overlay && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      setMobileExpanded(false);
      if (pathname === event.currentTarget.pathname) toggle.current?.focus();
    }
  }

  function navLinks(items: typeof NAV) {
    return items.map(({ href, label, icon }) => {
      const active = pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
      return (
        <Link
          key={href}
          href={href}
          className={styles.link}
          aria-current={active ? "page" : undefined}
          aria-label={label}
          title={expanded ? undefined : label}
          onClick={closeAfterNavigation}
        >
          <Icon path={icon} />
          <span className={styles.label}>{label}</span>
        </Link>
      );
    });
  }

  return (
    <div className={styles.shell} data-expanded={expanded}>
      {overlay && <button type="button" className={styles.scrim} tabIndex={-1} aria-label="Закрыть боковую панель" onClick={() => { setMobileExpanded(false); toggle.current?.focus(); }} />}
      <aside className={styles.rail} aria-label="Боковая панель Landway">
        <div className={styles.sidebar}>
          <button
            ref={toggle}
            type="button"
            className={styles.toggle}
            aria-expanded={expanded}
            aria-controls="landway-sidebar-navigation"
            aria-label={expanded ? "Свернуть боковую панель" : "Развернуть боковую панель"}
            title={expanded ? "Свернуть боковую панель" : "Развернуть боковую панель"}
            onClick={() => mobile ? setMobileExpanded(value => !value) : setDesktopExpanded(value => !value)}
          >
            <img className={styles.monogram} src="/landway-mark.svg" alt="" width={34} height={34} />
            <span className={styles.collapseIcon}><Icon path="M3 5h18v14H3z M9 5v14 M16 9l-3 3 3 3" /></span>
          </button>
          <div className={styles.wordmark}>
            <img src="/landway-wordmark.svg" alt="LANDWAY" width={445} height={58} />
            <span>Логист коридора Север — Юг</span>
          </div>
          <div className={styles.navigation} id="landway-sidebar-navigation">
            <nav className={styles.nav} aria-label="Разделы">
              {navLinks(NAV)}
            </nav>
            <div className={styles.account}>
              {user && (
                <div className={styles.user}>
                  <strong>{user.name}</strong>
                  <span>{user.role}</span>
                </div>
              )}
              <nav className={styles.nav} aria-label="Аккаунт">
                {navLinks(EXTRA)}
              </nav>
            </div>
          </div>
        </div>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
