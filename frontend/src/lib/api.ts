import type { ApiErrorBody } from "@/api/types";

/**
 * API klienti.
 * - Access token faqat xotirada (localStorage'da emas — XSS'dan himoya).
 * - Refresh token httpOnly cookie'da; 401 bo'lsa bir marta yangilab, so'rov qaytariladi.
 * - Bir vaqtda kelgan 401'lar bitta refresh so'roviga birlashtiriladi.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = null,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export const tokenStore = {
  set(token: string | null) {
    accessToken = token;
  },
  get: () => accessToken,
  onExpired(cb: () => void) {
    onSessionExpired = cb;
  },
};

const BASE = "/api/v1";

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(res.status, "network_error", "Server bilan aloqa yo'q");
  }
}

export async function refreshAccess(): Promise<string | null> {
  refreshing ??= fetch(`${BASE}/auth/refresh/`, { method: "POST", credentials: "include" })
    .then(async (res) => {
      if (!res.ok) return null;
      const data = (await res.json()) as { access: string };
      return data.access;
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null;
    });
  const token = await refreshing;
  accessToken = token;
  return token;
}

type Query = Record<string, string | number | boolean | undefined | null>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: Query): string {
  const url = `${BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function api<T>(path: string, opts: RequestOptions = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: "include",
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "Internet aloqasi yo'q");
  }

  if (res.status === 401 && retry) {
    const token = await refreshAccess();
    if (token) return api<T>(path, opts, false);
    onSessionExpired?.();
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fayl yuklash (multipart). */
export async function apiUpload<T>(path: string, form: FormData, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form, headers, credentials: "include" });
  if (res.status === 401 && retry && (await refreshAccess())) return apiUpload<T>(path, form, false);
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

/** Faylni (Excel) yuklab olish. */
export async function apiDownload(path: string, filename: string, query?: Query, retry = true): Promise<void> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(buildUrl(path, query), { headers, credentials: "include" });
  if (res.status === 401 && retry && (await refreshAccess())) return apiDownload(path, filename, query, false);
  if (!res.ok) throw await parseError(res);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
