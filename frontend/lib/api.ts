import { authHeaders, clearToken, getToken } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401 && typeof window !== "undefined") {
    clearToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("Требуется авторизация");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const text = (detail as { detail?: string }).detail;
    throw new Error(text || (await res.text()) || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", headers: authHeaders(false) });
  return handleResponse<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers: authHeaders(false), body: form });
  return handleResponse<T>(res);
}

export function documentFileUrl(documentId: string): string {
  const token = getToken();
  const base = `${BASE}/documents/${documentId}/file`;
  return token ? `${base}?access_token=${encodeURIComponent(token)}` : base;
}
