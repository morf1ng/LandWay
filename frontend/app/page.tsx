"use client";

import Link from "next/link";
import styles from "./dashboard.module.css";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { RecentShipments } from "@/components/shipments/RecentShipments";
import { toShipmentCardData } from "@/lib/shipments/adapters";

type Dashboard = {
  stats: {
    total: number;
    inTransit: number;
    delivered: number;
    atRisk: number;
    awaiting: number;
  };
  recent: Array<{
    id: string;
    name: string;
    origin: string;
    destination: string;
    status: string;
    predictedArrival: string;
    riskLevel: string;
    probability: number;
  }>;
  warnings: Array<{
    id: string;
    title: string;
    description: string;
    href: string;
    severity: string;
  }>;
  ports: Array<{
    name: string;
    workload: number;
    waitingShipments: number;
    weather: string;
    delayNote: string;
  }>;
  lastRecalculatedAt: string | null;
};

export default function HomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<Dashboard>("/dashboard")
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  if (error) return <p className="error">Не удалось загрузить панель: {error}. Запущен ли backend на :8000?</p>;
  if (!data) return <p>Загрузка…</p>;

  const s = data.stats;

  return (
    <div className={styles.dashboard}>
      <h1>Главная панель</h1>
      {data.lastRecalculatedAt && (
        <p className={styles.updated}>Последний пересчёт прогноза: {new Date(data.lastRecalculatedAt).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })}</p>
      )}

      <section className={styles.metrics} aria-label="Сводка по грузам">
        {[
          { title: "Всего грузов", value: s.total, note: `Ожидают отправки: ${s.awaiting}`, tone: "plain" },
          { title: "В пути", value: s.inTransit, tone: "dark" },
          { title: "Доставлено", value: s.delivered, tone: "plain" },
          { title: "С риском задержки", value: s.atRisk, note: data.warnings[0]?.title, tone: "accent" },
        ].map(({ title, value, note, tone }) => (
          <article className={styles.metric} data-tone={tone} key={title}>
            <h2>{title}</h2>
            {note && <p>{note}</p>}
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className={styles.shipments} aria-labelledby="shipments-title">
        <RecentShipments titleId="shipments-title" items={data.recent.map(toShipmentCardData)} />
      </section>

      <details className={styles.details}>
        <summary>Предупреждения и сводка по портам</summary>
      <section>
        <h2>Предупреждения</h2>
        {data.warnings.length === 0 ? (
          <p className="muted">Активных предупреждений нет.</p>
        ) : (
          <ul>
            {data.warnings.map((w) => (
              <li key={w.id}>
                <Link href={w.href}>
                  [{w.severity}] {w.title}: {w.description}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Сводка по портам</h2>
        <table>
          <thead>
            <tr>
              <th>Порт</th>
              <th>Загруженность, %</th>
              <th>Ожидающие грузы</th>
              <th>Погода</th>
              <th>Задержки</th>
            </tr>
          </thead>
          <tbody>
            {data.ports.map((p) => (
              <tr key={p.name}>
                <td>{p.name}</td>
                <td>{p.workload}</td>
                <td>{p.waitingShipments}</td>
                <td>{p.weather}</td>
                <td>{p.delayNote}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      </details>
    </div>
  );
}
