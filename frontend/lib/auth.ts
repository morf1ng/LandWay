const TOKEN_KEY = "sct_auth_token";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export type AuthUser = {
  id: string;
  username: string;
  name: string;
  role: string;
  organization: string;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(json = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (json) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function loginRequest(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { detail?: string }).detail || "Ошибка входа");
  }
  return data as { token: string; expiresAt: string; user: AuthUser };
}

export async function logoutRequest() {
  const token = getToken();
  if (!token) return;
  await fetch(`${API}/auth/logout`, {
    method: "POST",
    headers: authHeaders(),
  }).catch(() => undefined);
  clearToken();
}

export async function fetchMe(timeoutMs = 10_000): Promise<AuthUser> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}/auth/me`, {
      headers: authHeaders(),
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) throw new Error("unauthorized");
    const data = (await res.json()) as { user: AuthUser };
    return data.user;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("backend_timeout");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
