import { useState } from "react";
import emanuelFace from "../assets/emanuel-face.png";

interface LoginScreenProps {
  onSubmit: (password: string) => Promise<void>;
}

export function LoginScreen({ onSubmit }: LoginScreenProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password || busy) return;

    setBusy(true);
    setError(null);
    try {
      await onSubmit(password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro inesperado.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="login__card" onSubmit={handleSubmit}>
        <img src={emanuelFace} alt="" className="login__face" />
        <h1 className="login__title">Consultoria Zanfra</h1>
        <p className="login__subtitle">treino &amp; dieta</p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="senha"
          autoFocus
          disabled={busy}
        />

        {error && <div className="login__error">{error}</div>}

        <button type="submit" disabled={busy || !password}>
          {busy ? "entrando..." : "entrar"}
        </button>
      </form>
    </div>
  );
}
