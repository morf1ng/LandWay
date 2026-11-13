"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type MouseEvent, type ReactNode } from "react";
import styles from "./Shell.module.css";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  tone?: "logout";
};

const NAV: NavItem[] = [
  { href: "/", label: "Главная панель", icon: "M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-7H10v7H5a1 1 0 0 1-1-1z" },
  {
    href: "/shipments",
    label: "Грузы",
    icon: "M5 9.5 12 5.5l7 4V18l-7 4-7-4V9.5z M12 5.5V22 M8.5 11.5v9.5 M15.5 11.5v9.5",
  },
  { href: "/map", label: "Карта перевозок", icon: "M12 21s6.2-4.4 6.2-10.5A6.2 6.2 0 1 0 5.8 10.5C5.8 16.6 12 21 12 21z M12 13.2a2.7 2.7 0 1 0 0-5.4 2.7 2.7 0 0 0 0 5.4z" },
  { href: "/analytics", label: "AI-прогнозирование", icon: "M4 18.5l4.5-7 3.5 2.8 4-7.5 4 2.7" },
  {
    href: "/routes",
    label: "Маршруты",
    icon: "M7.25 16.75a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z M16.75 9.75a2.25 2.25 0 1 0 0 4.5 2.25 2.25 0 0 0 0-4.5z M9.4 14.8c2.2-1.6 4.3-3.2 7.2-5.8",
  },
  { href: "/customs", label: "Таможня и документы", icon: "M7 3.5h7.5L19 8v12.5H7V3.5z M14.5 3.5V8H19 M10 12.5h8 M10 16h8" },
  { href: "/ecology", label: "Экологическая аналитика", icon: "M12 20c-4.5-6.5-6.5-11.5-6-16 3.2 1.8 5 3.6 6 5.5 1.5-3.2 4-5.5 6-5.8-.2 5.5-2 10-6 16.3z" },
];

const EXTRA: NavItem[] = [
  { href: "/notifications", label: "Уведомления", icon: "M18 8.2A6 6 0 0 0 6 8.2c0 7.2-3.5 7.2-3.5 9.3h19c0-2.1-3.5-2.1-3.5-9.3z M9.5 21h5" },
  { href: "/profile", label: "Профиль", icon: "M20 21v-1.8a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4V21 M12 11.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
  { href: "/logout", label: "Выход", icon: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9", tone: "logout" },
];

const SIDEBAR_KEY = "landway:sidebar-expanded";
const mobileQuery = "(max-width: 760px)";

function subscribeToViewport(onChange: () => void) {
  const media = window.matchMedia(mobileQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}
const isMobileViewport = () => window.matchMedia(mobileQuery).matches;
const serverViewport = () => false;

function readSidebarExpanded(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) !== "0";
  } catch {
    return true;
  }
}

function NavIcon({ path, className }: { path: string; className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const mobile = useSyncExternalStore(subscribeToViewport, isMobileViewport, serverViewport);
  const [desktopExpanded, setDesktopExpanded] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const expanded = mobile ? mobileExpanded : desktopExpanded;
  const overlay = mobile && mobileExpanded;

  useEffect(() => {
    setDesktopExpanded(readSidebarExpanded());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || mobile) return;
    try {
      localStorage.setItem(SIDEBAR_KEY, desktopExpanded ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [desktopExpanded, hydrated, mobile]);

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

  function navLinks(items: NavItem[]) {
    return items.map(({ href, label, icon, tone }) => {
      const active = pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
      return (
        <Link
          key={href}
          href={href}
          className={styles.link}
          data-tone={tone}
          aria-current={active ? "page" : undefined}
          aria-label={label}
          title={!expanded ? label : undefined}
          onClick={closeAfterNavigation}
        >
          <span className={styles.label}>{label}</span>
          <span className={styles.linkIconSlot}>
            <NavIcon path={icon} className={styles.navIcon} />
          </span>
        </Link>
      );
    });
  }

  return (
    <div className={styles.shell} data-expanded={expanded} data-hydrated={hydrated || undefined}>
      {overlay && (
        <button
          type="button"
          className={styles.scrim}
          tabIndex={-1}
          aria-label="Закрыть боковую панель"
          onClick={() => {
            setMobileExpanded(false);
            toggle.current?.focus();
          }}
        />
      )}
      <aside className={styles.rail} aria-label="Боковая панель Landway">
        <div className={styles.sidebar}>
          <div className={styles.sidebarHead}>
            <button
              ref={toggle}
              type="button"
              className={styles.toggle}
              aria-expanded={expanded}
              aria-controls="landway-sidebar-navigation"
              aria-label={expanded ? "Свернуть боковую панель" : "Развернуть боковую панель"}
              title={expanded ? "Свернуть боковую панель" : "Развернуть боковую панель"}
              onClick={() => (mobile ? setMobileExpanded((value) => !value) : setDesktopExpanded((value) => !value))}
            >
              <img className={styles.monogram} src="/landway-mark.svg" alt="" width={44} height={44} />
              <NavIcon path="M14 8l-4 4 4 4" className={styles.toggleIcon} />
            </button>
          </div>
          <div className={styles.wordmark}>
            <img src="/landway-wordmark.svg" alt="LANDWAY" width={445} height={58} />
            <span>Логист коридора Север — Юг</span>
          </div>
          <div className={styles.navigation} id="landway-sidebar-navigation">
            <nav className={styles.nav} aria-label="Разделы">
              {navLinks(NAV)}
            </nav>
            <div className={styles.account}>
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
