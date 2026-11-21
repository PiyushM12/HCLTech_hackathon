// The browser sends the server's session cookie on same-origin requests.
import type {
  Account,
  AccountRole,
  AdminLoadResponse,
  AskRequest,
  AskResponse,
  AuditRecord,
  CancelResponse,
  ConfirmResponse,
  Conversation,
  ConversationSummary,
  EligibilityAttributes,
  EligibilityRequest,
  EligibilityResponse,
  HealthResponse,
  IngestMetadata,
  IngestResponse,
  ReferralRecord,
  Scheme,
  Verdict,
  SourceDetail,
  SourceRow,
} from "./types";

export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
  /** True when the server could not be reached at all. */
  get isNetwork(): boolean {
    return this.status === 0;
  }
}

function detailToString(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, type}]
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  if (detail == null) return "";
  return JSON.stringify(detail);
}

interface RequestOptions {
  method?: "GET" | "POST";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form; // browser sets the multipart boundary
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "Could not reach the SchemeSathi server.");
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in (data as Record<string, unknown>)
        ? detailToString((data as Record<string, unknown>).detail)
        : typeof data === "string"
          ? data.slice(0, 300)
          : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

const enc = encodeURIComponent;

export const api = {
  login: (role: AccountRole, username: string, password: string) =>
    request<{ account: Account }>("/auth/login", { json: { role, username, password } }),

  register: (username: string, password: string, consent: boolean) =>
    request<{ account: Account }>("/auth/register", { json: { username, password, consent } }),

  logout: () => request<null>("/auth/logout", { method: "POST" }),

  me: () => request<{ account: Account | null }>("/auth/me"),

  ask: (body: AskRequest, signal?: AbortSignal) =>
    request<AskResponse>("/ask", { json: { channel: "web", ...body }, signal }),

  confirmAction: (actionId: string) =>
    request<ConfirmResponse>(`/actions/${enc(actionId)}/confirm`, { method: "POST", json: {} }),

  cancelAction: (actionId: string) =>
    request<CancelResponse>(`/actions/${enc(actionId)}/cancel`, { method: "POST", json: {} }),

  eligibility: (body: EligibilityRequest) => request<EligibilityResponse>("/eligibility", { json: body }),

  schemes: (asOfDate?: string) => request<Scheme[]>(`/schemes${asOfDate ? `?as_of_date=${enc(asOfDate)}` : ""}`),

  recommendedSchemes: (attributes: EligibilityAttributes | null, asOfDate?: string, conversationId?: string) =>
    request<(Scheme & { verdict: Verdict })[]>("/schemes/recommendations", {
      json: { attributes, as_of_date: asOfDate, conversation_id: conversationId },
    }),

  sources: () => request<SourceRow[]>("/sources"),

  source: (sourceId: string) => request<SourceDetail>(`/sources/${enc(sourceId)}`),

  referral: (referralId: string) => request<ReferralRecord>(`/referrals/${enc(referralId)}`),

  audit: (traceId: string) => request<AuditRecord>(`/audit/${enc(traceId)}`),

  conversations: () => request<ConversationSummary[]>("/conversations"),

  conversation: (id: string, signal?: AbortSignal) => request<Conversation>(`/conversations/${enc(id)}`, { signal }),

  health: () => request<HealthResponse>("/health"),

  ingest: (file: File, metadata: IngestMetadata) => {
    const form = new FormData();
    form.append("file", file);
    form.append("metadata", JSON.stringify(metadata));
    return request<IngestResponse>("/ingest", { form, method: "POST" });
  },

  adminLoad: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f, f.name));
    return request<AdminLoadResponse>("/admin/load", { form, method: "POST" });
  },
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail || err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}
