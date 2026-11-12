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
    <>
      <h1>ИИ-аналитика и прогнозирование</h1>
      <p className="muted">{data.disclaimer}</p>
      <p>
        <button type="button" onClick={recalculate}>
          Пересчитать прогноз
        </button>
        {data.calculatedAt && <span className="muted"> Последний расчёт: {data.calculatedAt}</span>}
      </p>

      <section>
        <h2>Все грузы</h2>
        <table>
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
                <td>
                  <button type="button" onClick={() => setDetailId(row.id)} style={{ border: 0, background: "none", padding: 0 }}>
                    {row.id}
                  </button>
                </td>
                <td>{row.route}</td>
                <td>
                  {row.probability}% ({riskLabel[row.riskLevel] ?? row.riskLevel})
                </td>
                <td>{row.reasons.join("; ")}</td>
                <td>{row.estimatedDelay}</td>
                <td>{row.recommendation}</td>
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
            <li>Прогноз доставки: {detail.predictedArrival}</li>
            <li>Задержка: {detail.estimatedDelay} ч</li>
            <li>Расчёт: {detail.calculatedAt}</li>
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
    </>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <AnalyticsInner />
    </Suspense>
  );
}
