export type ChatMessage = {
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

export type ChatResponse = {
  conversation_id: string;
  intent: string;
  action: string;
  confidence: number;
  tool_success: boolean;
  message: string;
  tool_data: Record<string, unknown>;
  required_slots: Record<string, boolean>;
  slots: Record<string, string>;
};

export type ToolRoute = "/tools/calculator" | "/tools/products" | "/tools/outlets";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class RateLimitError extends Error {
  status = 429 as const;
  retryAfterSeconds: number;
  limit?: number;
  remaining?: number;
  resetEpoch?: number;
  constructor(message: string, init: { retryAfterSeconds: number; limit?: number; remaining?: number; resetEpoch?: number }) {
    super(message);
    this.name = "RateLimitError";
    this.retryAfterSeconds = init.retryAfterSeconds;
    this.limit = init.limit;
    this.remaining = init.remaining;
    this.resetEpoch = init.resetEpoch;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    // Handle 429 with structured error, using headers for guidance
    if (response.status === 429) {
      type RateLimitBody = { error?: string; message?: string; retry_after_seconds?: number };
      let body: RateLimitBody = {};
      try {
        const parsed = (await response.json()) as unknown;
        if (parsed && typeof parsed === "object") {
          body = parsed as RateLimitBody;
        }
      } catch (_) {
        // ignore
      }
      const retry = Number(response.headers.get("Retry-After") ?? body.retry_after_seconds ?? 0);
      const limit = Number(response.headers.get("X-RateLimit-Limit") ?? NaN);
      const remaining = Number(response.headers.get("X-RateLimit-Remaining") ?? NaN);
      const reset = Number(response.headers.get("X-RateLimit-Reset") ?? NaN);
      const message = body?.message || "Too many requests. Please retry later.";
      throw new RateLimitError(message, {
        retryAfterSeconds: isNaN(retry) ? 0 : retry,
        limit: isNaN(limit) ? undefined : limit,
        remaining: isNaN(remaining) ? undefined : remaining,
        resetEpoch: isNaN(reset) ? undefined : reset,
      });
    }

    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.detail ?? error.message ?? "Request failed");
  }

  return (await response.json()) as T;
}

export async function sendChatMessage(payload: {
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
}): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function callTool(path: ToolRoute, params: Record<string, string>): Promise<unknown> {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params).forEach(([key, value]) => url.searchParams.append(key, value));
  return request<unknown>(url.pathname + url.search);
}

export async function fetchMetrics(): Promise<unknown> {
  return request<unknown>("/metrics");
}
