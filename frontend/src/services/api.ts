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
};

export type ToolRoute = "/tools/calculator" | "/tools/products" | "/tools/outlets";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
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
