"use client";

import Link from "next/link";
import styles from "./dashboard.module.css";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { RecentShipments } from "@/components/shipments/RecentShipments";
import { toShipmentCardData } from "@/lib/shipments/adapters";
import { formatDateTime } from "@/lib/format";

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
    shipmentId?: string;
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
  const warningsByShipment = new Map<string, Dashboard["warnings"]>();
  for (const warning of data.warnings) {
    const shipmentId = warning.shipmentId ?? warning.id.split(":")[0];
    if (!data.recent.some((shipment) => shipment.id === shipmentId)) continue;
    const shipmentWarnings = warningsByShipment.get(shipmentId) ?? [];
    // The backend can report weather and wind as separate notifications of one event.
    if (!shipmentWarnings.some((item) => item.title === warning.title)) shipmentWarnings.push(warning);
    warningsByShipment.set(shipmentId, shipmentWarnings);
  }
  const warnings = Array.from(warningsByShipment, ([shipmentId, causes]) => ({
    shipmentId,
    causes,
    shipment: data.recent.find((item) => item.id === shipmentId)!,
  }));
  const severityLabel: Record<string, string> = {
    high: "Высокий риск",
    medium: "Требует внимания",
    low: "Информация",
  };

  return (
    <div className={styles.dashboard}>
      <h1>Главная панель</h1>
      {data.lastRecalculatedAt && (
        <p className={styles.updated}>Последний пересчёт прогноза: {formatDateTime(data.lastRecalculatedAt, true)}</p>
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

      <section className={styles.alerts} aria-labelledby="alerts-title">
        <div className={styles.sectionHead}>
          <h2 id="alerts-title">Предупреждения</h2>
          <Link className={styles.allLink} href="/notifications">Смотреть все →</Link>
        </div>
        {warnings.length === 0 ? (
          <p className={styles.emptyState}>Активных предупреждений нет.</p>
        ) : (
          <div className={styles.alertGrid}>
            {warnings.map(({ shipmentId, shipment, causes }) => {
              return (
                <article className={styles.alertCard} data-severity={causes[0].severity} key={shipmentId}>
                  <span className={styles.severity}>{severityLabel[causes[0].severity] ?? "Событие"} · {causes.length} {causes.length === 1 ? "причина" : causes.length < 5 ? "причины" : "причин"}</span>
                  <h3>{shipment.origin} → {shipment.destination}</h3>
                  <ul className={styles.alertCauses}>
                    {causes.map((cause) => (
                      <li key={cause.id}>{cause.description.replace(new RegExp(`^${shipmentId}[.:]\\s*`), "")}</li>
                    ))}
                  </ul>
                  <div className={styles.alertActions}>
                    <Link className={styles.shipmentLink} href={`/shipments/${encodeURIComponent(shipmentId)}`}>{shipmentId}</Link>
                    <Link className={styles.forecastLink} href={`/analytics?shipment=${encodeURIComponent(shipmentId)}`}>Прогноз</Link>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className={styles.ports} aria-labelledby="ports-title">
        <div className={styles.sectionHead}>
          <h2 id="ports-title">Сводка по портам</h2>
          <span className={styles.demoBadge}>Демо</span>
        </div>
        <p className={styles.portNote}>Загруженность и погода — демонстрационные показатели. Ожидающие грузы подсчитаны по текущим данным приложения.</p>
        <div className={styles.portTableWrap}>
          <table className={styles.portTable}>
            <thead>
              <tr>
                <th>Порт</th>
                <th>Загруженность</th>
                <th>Ожидающие грузы</th>
                <th>Погода</th>
                <th>Задержки</th>
              </tr>
            </thead>
            <tbody>
              {data.ports.map((port) => (
                <tr key={port.name}>
                  <td data-label="Порт">{port.name}</td>
                  <td data-label="Загруженность">{port.workload}%</td>
                  <td data-label="Ожидающие грузы">{port.waitingShipments}</td>
                  <td data-label="Погода">{port.weather}</td>
                  <td data-label="Задержки">{port.delayNote}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
