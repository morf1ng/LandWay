"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel } from "@/lib/labels";

type Analytics = {
  disclaimer: string;
  calculatedAt: string | null;
  rows: Array<{
    id: string;
    route: string;
    probability: number;
    riskLevel: string;
    reasons: string[];
    estimatedDelay: number;
    predictedArrival: string;
    recommendation: string;
    calculatedAt: string;
  }>;
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function AnalyticsInner() {
  const search = useSearchParams();
  const focus = search.get("shipment");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState<string | null>(focus);

  function load() {
    apiGet<Analytics>("/analytics")
      .then((d) => {
        setData(d);
        if (focus) setDetailId(focus);
      })
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    load();
  }, [focus]);

  async function recalculate() {
    setError("");
    try {
      const d = await apiPost<Analytics>("/analytics/recalculate", {});
      setData(d);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Загрузка…</p>;

  const detail = data.rows.find((r) => r.id === detailId);

  return (
    <div className="appPage">
      <h1>ИИ-аналитика и прогнозирование</h1>
      <p className="pageLead">{data.disclaimer}</p>
      <div className="actionRow">
        <button type="button" className="primaryAction" onClick={recalculate}>
          Пересчитать прогноз
        </button>
        {data.calculatedAt && <span className="muted">Последний расчёт: {formatDate(data.calculatedAt)}</span>}
      </div>

      <section>
        <h2>Все грузы</h2>
        <table className="analyticsTable">
          <thead>
            <tr>
              <th>ID</th>
              <th>Маршрут</th>
              <th>Вероятность</th>
              <th>Причины</th>
              <th>Задержка, ч</th>
              <th>Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.id}>
                <td data-label="Груз">
                  <button type="button" onClick={() => setDetailId(row.id)}>
                    {row.id}
                  </button>
                </td>
                <td data-label="Маршрут">{row.route}</td>
                <td data-label="Вероятность">
                  {row.probability}% ({riskLabel[row.riskLevel] ?? row.riskLevel})
                </td>
                <td data-label="Причины">{row.reasons.join("; ")}</td>
                <td data-label="Задержка">{row.estimatedDelay} ч</td>
                <td data-label="Рекомендация">{row.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {detail && (
        <section>
          <h2>Детальный прогноз: {detail.id}</h2>
          <ul>
            <li>Вероятность задержки: {detail.probability}%</li>
            <li>Уровень: {riskLabel[detail.riskLevel] ?? detail.riskLevel}</li>
            <li>Прогноз доставки: {formatDate(detail.predictedArrival)}</li>
            <li>Задержка: {detail.estimatedDelay} ч</li>
            <li>Расчёт: {formatDate(detail.calculatedAt)}</li>
          </ul>
          <p>Причины:</p>
          <ul>
            {detail.reasons.map((r, i) => (
              <li key={i}>
                {r}
              </li>
            ))}
          </ul>
          <p>Рекомендация: {detail.recommendation}</p>
          <Link className="button-link" href={`/shipments/${detail.id}`}>
            Карточка груза
          </Link>
        </section>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <AnalyticsInner />
    </Suspense>
  );
}
