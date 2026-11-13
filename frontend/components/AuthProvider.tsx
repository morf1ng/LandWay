"use client";

import { Shell } from "@/components/Shell";
import { AuthUser, clearToken, fetchMe, getToken } from "@/lib/auth";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, createContext, useContext, useEffect, useState } from "react";

type AuthContextValue = {
  user: AuthUser | null;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({ user: null, refreshUser: async () => {} });

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(isLogin);
  const [bootError, setBootError] = useState("");

  async function refreshUser() {
    const me = await fetchMe();
    setUser(me);
  }

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      if (isLogin) {
        setReady(true);
        return;
      }

      const token = getToken();
      if (!token) {
        setReady(true);
        router.replace("/login");
        return;
      }

      try {
        const me = await fetchMe();
        if (cancelled) return;
        setBootError("");
        setUser(me);
        setReady(true);
      } catch {
        if (cancelled) return;
        clearToken();
        setUser(null);
        setReady(true);
        setBootError("Сессия устарела или backend не отвечает. Войдите снова.");
        router.replace("/login");
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [isLogin, pathname, router]);

  if (!ready) {
    return (
      <div style={{ padding: 24, maxWidth: 480 }}>
        <p>Проверка сессии…</p>
        <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
          Должны быть запущены frontend (:3000) и backend (:8000). Логин: <strong>logist</strong> / <strong>demo123</strong>
        </p>
      </div>
    );
  }

  if (isLogin) {
    return (
      <>
        {bootError ? <p className="error" style={{ padding: "12px 16px 0", margin: 0 }}>{bootError}</p> : null}
        {children}
      </>
    );
  }

  if (!user) {
    return <p style={{ padding: 24 }}>Переход на страницу входа…</p>;
  }

  return (
    <AuthContext.Provider value={{ user, refreshUser }}>
      <Shell>{children}</Shell>
    </AuthContext.Provider>
  );
}
