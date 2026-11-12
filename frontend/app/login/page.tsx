"use client";

import { loginRequest, setToken } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import styles from "./login.module.css";
import { TruckOrbit } from "./TruckOrbit";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
    <div className={styles.page}>
      <span className={`${styles.circle} ${styles.cPurpleLg}`} aria-hidden />
      <span className={`${styles.circle} ${styles.cBlackTop}`} aria-hidden />
      <span className={`${styles.circle} ${styles.cBlackMid}`} aria-hidden />
      <span className={`${styles.circle} ${styles.cPurpleBottom}`} aria-hidden />
      <span className={`${styles.circle} ${styles.cPurpleSm}`} aria-hidden />
      <TruckOrbit />

      <div className={styles.card}>
        <h1 className={styles.logo}><img src="/landway-wordmark.svg" alt="LANDWAY" width={445} height={58} /></h1>
        <p className={styles.title}>Вход в систему</p>

        {error && <p className={styles.error}>{error}</p>}

        <form className={styles.form} onSubmit={onSubmit}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="username">
              Логин
            </label>
            <input
              id="username"
              className={styles.input}
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="password">
              Пароль
            </label>
            <input
              id="password"
              className={styles.input}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className={styles.submit} disabled={loading}>
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
