import { authHeaders, clearToken, getToken } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg ?? JSON.stringify(item)).join("; ");
  }
  return "";
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError("Сервер недоступен. Проверьте, что бэкенд запущен, и повторите попытку.", 0);
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401 && typeof window !== "undefined") {
    clearToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError("Требуется авторизация", 401);
  }
  if (!res.ok) {
    const raw = await res.text();
    let message = "";
    try {
      message = describeDetail((JSON.parse(raw) as { detail?: unknown }).detail);
    } catch {
      message = raw;
    }
    throw new ApiError(message || `Ошибка сервера (${res.status})`, res.status);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await send(path, { cache: "no-store", headers: authHeaders(false) });
  return handleResponse<T>(res);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await send(path, {
    method: "POST",
    headers: authHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await send(path, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await send(path, { method: "POST", headers: authHeaders(false), body: form });
  return handleResponse<T>(res);
}

export function documentFileUrl(documentId: string): string {
  const token = getToken();
  const base = `${BASE}/documents/${documentId}/file`;
  return token ? `${base}?access_token=${encodeURIComponent(token)}` : base;
}
