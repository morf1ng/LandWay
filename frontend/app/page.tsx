"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { riskLabel, statusLabel } from "@/lib/labels";

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
    <>
      <h1>Главная панель</h1>
      {data.lastRecalculatedAt && (
        <p className="muted">Последний пересчёт прогноза: {data.lastRecalculatedAt}</p>
      )}

      <section>
        <h2>Общая статистика</h2>
        <ul>
          <li>Всего грузов: {s.total}</li>
          <li>В пути: {s.inTransit}</li>
          <li>Доставлено: {s.delivered}</li>
          <li>С риском задержки: {s.atRisk}</li>
          <li>Ожидают отправки: {s.awaiting}</li>
        </ul>
      </section>

      <section>
        <h2>Последние перевозки</h2>
        <table>
          <thead>
            <tr>
              <th>Номер</th>
              <th>Название</th>
              <th>Откуда</th>
              <th>Куда</th>
              <th>Статус</th>
              <th>Прогноз доставки</th>
              <th>Риск</th>
            </tr>
          </thead>
          <tbody>
            {data.recent.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/shipments/${row.id}`}>{row.id}</Link>
                </td>
                <td>{row.name}</td>
                <td>{row.origin}</td>
                <td>{row.destination}</td>
                <td>{statusLabel[row.status] ?? row.status}</td>
                <td>{row.predictedArrival}</td>
                <td>
                  {riskLabel[row.riskLevel] ?? row.riskLevel} ({row.probability}%)
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

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
    </>
  );
}
