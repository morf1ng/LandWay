"use client";

import { loginRequest, setToken } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("logist");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { token } = await loginRequest(username, password);
      setToken(token);
      router.replace("/");
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 360, margin: "48px auto", padding: 16 }}>
      <h1>Smart Caspian Transit</h1>
      <p className="muted">Вход в демонстрационную платформу</p>
      {error && <p className="error">{error}</p>}
      <form onSubmit={onSubmit}>
        <p>
          <label>
            Логин
            <br />
            <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
        </p>
        <p>
          <label>
            Пароль
            <br />
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        </p>
        <button type="submit" disabled={loading}>
          {loading ? "Вход…" : "Войти"}
        </button>
      </form>
      <p className="muted" style={{ marginTop: 24 }}>
        Демо-доступ: <strong>logist</strong> / <strong>demo123</strong> или <strong>admin</strong> / <strong>admin123</strong>
      </p>
    </main>
  );
}
