import { API_BASE_URL } from "./endpoints";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

const REQUEST_TIMEOUT_MS = 15_000;

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text.length > 0 ? text : null;
}

function mergeAbortSignals(a: AbortSignal, b?: AbortSignal | null): AbortSignal {
  if (!b) {
    return a;
  }
  const abortSignalWithAny = AbortSignal as typeof AbortSignal & {
    any?: (signals: AbortSignal[]) => AbortSignal;
  };
  if (typeof abortSignalWithAny.any === "function") {
    return abortSignalWithAny.any([a, b]);
  }

  const fallbackController = new AbortController();
  const abort = () => fallbackController.abort();
  a.addEventListener("abort", abort, { once: true });
  b.addEventListener("abort", abort, { once: true });
  return fallbackController.signal;
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const timeoutController = new AbortController();
  const timeoutId = window.setTimeout(() => timeoutController.abort(), REQUEST_TIMEOUT_MS);

  try {
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type") && init.body) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Accept", "application/json");
    headers.set("X-Request-ID", createRequestId());

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: mergeAbortSignals(timeoutController.signal, init.signal),
    });

    const body = await parseBody(response);
    if (!response.ok) {
      const message =
        typeof body === "object" && body !== null && "detail" in body
          ? String((body as { detail: unknown }).detail)
          : `Request failed (${response.status})`;
      throw new ApiError(message, response.status, body);
    }

    return body as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Request timed out or was cancelled", 408, null);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
