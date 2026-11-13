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
  const [showPassword, setShowPassword] = useState(false);

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
            <div className={styles.passwordWrap}>
              <input
                id="password"
                className={styles.input}
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className={styles.passwordToggle}
                aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
                    <path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M6.7 6.7C4.6 8.1 3 10 2 12c2.5 4 6.3 7 10 7 1.6 0 3.1-.4 4.5-1M9.3 5.2A10.5 10.5 0 0 1 12 5c3.7 0 7.5 3 10 7-.8 1.3-1.8 2.5-3 3.5" />
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <button type="submit" className={styles.submit} disabled={loading}>
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
