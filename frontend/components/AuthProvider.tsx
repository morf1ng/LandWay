"use client";

import { Shell } from "@/components/Shell";
import { AuthUser, fetchMe, getToken } from "@/lib/auth";
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

  async function refreshUser() {
    const me = await fetchMe();
    setUser(me);
  }

  useEffect(() => {
    if (isLogin) {
      setReady(true);
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then((me) => {
        setUser(me);
        setReady(true);
      })
      .catch(() => {
        router.replace("/login");
      });
  }, [isLogin, pathname, router]);

  if (!ready) return <p style={{ padding: 16 }}>Проверка сессии…</p>;

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <AuthContext.Provider value={{ user, refreshUser }}>
      <Shell user={user}>{children}</Shell>
    </AuthContext.Provider>
  );
}
