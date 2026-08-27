import type { ChatResponse } from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const OVERVIEW_URL = `${API_URL}/overview.html`;

export async function sendMessage(threadId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
