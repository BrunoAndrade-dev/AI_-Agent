/** Browser-only transport. Identity and conversation ownership stay in Django. */

export type Session = {
  authenticated: boolean;
  csrf_token: string;
  expires_at: string | null;
};
export type Conversation = {
  id: string;
  created_at: string;
  updated_at: string;
};
export type Source = {
  source: string;
  version: string;
  page: number;
  section: string;
};
export type Turn = {
  id: string;
  request_id: string;
  user_message: string;
  text: string;
  status: string;
  sources: Source[];
  tools_used: string[];
  validation_errors: string[];
  created_at: string;
};
export type History = {
  conversation_id: string;
  turns: Turn[];
  max_turns: number;
};
export type ConversationPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Conversation[];
};
export type MessageJob = {
  conversationId: string;
  requestId: string;
  text: string;
};
export type TurnResult = { turn: Turn; replayed: boolean };

export class ApiError extends Error {
  status: number;
  code: string;
  retryAfter: number;
  constructor(status: number, code: string, message: string, retryAfter = 0) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

const DEFAULT_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export class StoreApi {
  private csrf = "";
  private base: string;

  constructor(base = DEFAULT_BASE) {
    this.base = base.replace(/\/+$/, "");
  }

  private async request<T>(
    path: string,
    method = "GET",
    data?: object,
    acceptsTurn = false,
    retryCsrf = true,
  ): Promise<T> {
    if (method !== "GET" && !this.csrf) await this.session();
    let response: Response;
    try {
      response = await fetch(`${this.base}${path}`, {
        method,
        credentials: "include",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(data ? { "Content-Type": "application/json" } : {}),
          ...(method !== "GET" ? { "X-CSRFToken": this.csrf } : {}),
        },
        ...(data ? { body: JSON.stringify(data) } : {}),
      });
    } catch {
      throw new ApiError(
        0,
        "network_error",
        "Não consegui conectar ao atendimento. Tente novamente.",
      );
    }
    if (response.status === 204) return undefined as T;
    let body;
    try {
      body = await response.json();
    } catch {
      throw new ApiError(
        response.status,
        "invalid_response",
        "O atendimento não respondeu como esperado.",
      );
    }
    if (!response.ok) {
      // A rejected CSRF request did not execute the operation; retry once with a fresh token.
      if (
        response.status === 403 &&
        retryCsrf &&
        body.error?.message?.startsWith("CSRF Failed:")
      ) {
        await this.session();
        return this.request<T>(path, method, data, acceptsTurn, false);
      }
      // Business failures are persisted turns; show their safe text, not a generic network error.
      if (acceptsTurn && body.turn?.id && typeof body.turn.text === "string")
        return body as T;
      throw new ApiError(
        response.status,
        body.error?.code || "request_failed",
        body.error?.message || "Não foi possível concluir. Tente novamente.",
        Math.max(0, Number(response.headers.get("Retry-After")) || 0),
      );
    }
    return body as T;
  }

  async session(): Promise<Session> {
    const state = await this.request<Session>("/chat/session/");
    this.csrf = state.csrf_token;
    return state;
  }

  async login(token: string): Promise<Session> {
    const state = await this.request<Session>("/chat/session/", "POST", {
      access_token: token,
    });
    this.csrf = state.csrf_token;
    return state;
  }

  async logout(): Promise<void> {
    await this.request<void>("/chat/session/", "DELETE");
    this.csrf = "";
  }

  conversations(page = 1): Promise<ConversationPage> {
    return this.request(`/chat/conversations/?page=${page}`);
  }

  createConversation(): Promise<Conversation> {
    return this.request("/chat/conversations/", "POST", {});
  }

  history(id: string): Promise<History> {
    return this.request(
      `/chat/conversations/${encodeURIComponent(id)}/messages/`,
    );
  }

  send(job: MessageJob): Promise<TurnResult> {
    return this.request(
      `/chat/conversations/${encodeURIComponent(job.conversationId)}/messages/`,
      "POST",
      { request_id: job.requestId, text: job.text },
      true,
    );
  }
}
