import type { ChatResponse, SessionStatus } from "./types";

// Empty by default: in production the frontend is served by the same origin
// as the API, so relative paths just work. Local dev sets VITE_API_URL to
// point at the separately-running backend.
export const API_URL = import.meta.env.VITE_API_URL ?? "";

export const OVERVIEW_URL = `${API_URL}/overview.html`;

export async function getSession(): Promise<SessionStatus> {
  const res = await fetch(`${API_URL}/api/session`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`Falha ao verificar sessão (HTTP ${res.status})`);
  }
  return res.json();
}

export async function login(password: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ password }),
  });

  if (res.status === 401) {
    throw new Error("Senha incorreta");
  }
  if (!res.ok) {
    throw new Error(`Falha ao entrar (HTTP ${res.status})`);
  }
}

export async function sendMessage(threadId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ thread_id: threadId, message }),
  });

  if (!res.ok) {
    throw new Error(`Falha ao falar com o assistente (HTTP ${res.status})`);
  }

  return res.json();
}

export function artifactSrc(artifactUrl: string): string {
  return artifactUrl.startsWith("http") ? artifactUrl : `${API_URL}${artifactUrl}`;
}
