export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
}

export interface ChatResponse {
  answer: string;
  artifact_url: string | null;
}
