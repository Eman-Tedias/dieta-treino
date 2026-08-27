import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";
import emanuelFace from "../assets/emanuel-face.png";

interface ChatPanelProps {
  messages: ChatMessage[];
  sending: boolean;
  onSend: (text: string) => void;
}

export function ChatPanel({ messages, sending, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    onSend(text);
    setDraft("");
  }

  const lastAssistantIndex = sending
    ? -1
    : messages.map((m) => m.role).lastIndexOf("assistant");

  return (
    <div className="chat-panel">
      <div className="chat-panel__messages" ref={listRef}>
        {messages.map((m, i) => {
          const speaking = !sending && i === lastAssistantIndex;
          return (
            <div key={m.id} className={`row row--${m.role}`}>
              {speaking && <img src={emanuelFace} alt="" className="avatar-speaking" />}
              <div className={`bubble bubble--${m.role}${speaking ? " bubble--speaking" : ""}`}>
                {m.text}
              </div>
            </div>
          );
        })}
        {sending && (
          <div className="row row--assistant">
            <img src={emanuelFace} alt="" className="avatar-speaking" />
            <div className="bubble bubble--assistant bubble--pending bubble--speaking">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      <form className="chat-panel__input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Pergunte sobre treino ou dieta..."
          disabled={sending}
        />
        <button type="submit" disabled={sending || !draft.trim()} aria-label="Enviar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 12L20 4L14 20L11 13L4 12Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </form>
    </div>
  );
}
