export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (response.status === 401) {
    const refreshed = await fetch("/api/auth/refresh", { method: "POST" });
    if (refreshed.ok) {
      response = await fetch(`/api/backend${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
        credentials: "same-origin",
        cache: "no-store",
      });
    } else {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      throw new ApiError(401, "Session expired");
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
