import { useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { DashboardPanel } from "./components/DashboardPanel";
import { sendMessage, artifactSrc, OVERVIEW_URL } from "./api";
import type { ChatMessage } from "./types";

function newId(): string {
  return crypto.randomUUID();
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "Faaaala Zanfra, qualquer dúvida que você tiver sobre meus dados de treino e dieta dos últimos tempos, manda aqui que eu mostro pra você",
};

export default function App() {
  const threadId = useRef(newId());
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [sending, setSending] = useState(false);
  const [dashboardUrl, setDashboardUrl] = useState<string>(OVERVIEW_URL);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(text: string) {
    setError(null);
    setMessages((prev) => [...prev, { id: newId(), role: "user", text }]);
    setSending(true);
    try {
      const res = await sendMessage(threadId.current, text);
      setMessages((prev) => [...prev, { id: newId(), role: "assistant", text: res.answer }]);
      if (res.artifact_url) {
        setDashboardUrl(artifactSrc(res.artifact_url));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__text">
          <span className="topbar__title">Consultoria Zanfra</span>
          <span className="topbar__subtitle">treino &amp; dieta</span>
        </div>
      </header>

      <DashboardPanel src={dashboardUrl} />

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-wrap">
        <ChatPanel messages={messages} sending={sending} onSend={handleSend} />
      </div>
    </div>
  );
}
