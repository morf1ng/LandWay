"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, FormEvent, useEffect, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { transportLabel } from "@/lib/labels";
import { formatKgCo2, formatNumber } from "@/lib/format";

type Ecology = {
  disclaimer: string;
  formula: string;
  factors: { rail: number; sea: number; road: number };
  total: number;
  byTransport: Record<string, number>;
  shipmentCount: number;
  rows: Array<{
    shipmentId: string;
    routeName: string;
    transportType: string;
    distance: number;
    co2Emission: number;
    from: string;
    to: string;
  }>;
  comparison: Array<{
    name: string;
    current: boolean;
    selectable: boolean;
    carbonFootprint: number;
    fullCarbonFootprint?: number;
  }>;
};

function EcologyInner() {
  const search = useSearchParams();
  const shipmentFilter = search.get("shipment") ?? "";
  const [data, setData] = useState<Ecology | null>(null);
  const [shipmentId, setShipmentId] = useState(shipmentFilter);
  const [factors, setFactors] = useState({ rail: 0.028, sea: 0.015, road: 0.095 });
  const [shipments, setShipments] = useState<Array<{ id: string }>>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  function load() {
    const q = shipmentId ? `?shipmentId=${encodeURIComponent(shipmentId)}` : "";
    apiGet<Ecology>(`/ecology${q}`)
      .then((d) => {
        setData(d);
        setFactors(d.factors);
      })
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    apiGet<Array<{ id: string }>>("/shipments").then(setShipments);
  }, []);

  useEffect(() => {
    setShipmentId(shipmentFilter);
  }, [shipmentFilter]);

  useEffect(() => {
    load();
  }, [shipmentId]);

  async function saveFactors(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiPatch("/ecology/factors", factors);
      setSaved("Коэффициенты сохранены, след пересчитан.");
      load();
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Загрузка…</p>;

  const comparison = data.comparison.filter((item) => item.current || item.selectable);

  return (
    <div className="appPage">
      <h1>Экологическая аналитика</h1>
      <p className="pageLead">{data.disclaimer}</p>
      <p>
        {data.formula} (кг CO₂ / т·км: поезд {data.factors.rail}, море {data.factors.sea}, авто {data.factors.road})
      </p>

      <section>
        <h2>Коэффициенты (демо)</h2>
        <form onSubmit={saveFactors}>
          <label>
            поезд{" "}
            <input
              type="number"
              step="0.001"
              value={factors.rail}
              onChange={(e) => setFactors({ ...factors, rail: Number(e.target.value) })}
            />
          </label>{" "}
          <label>
            море{" "}
            <input
              type="number"
              step="0.001"
              value={factors.sea}
              onChange={(e) => setFactors({ ...factors, sea: Number(e.target.value) })}
            />
          </label>{" "}
          <label>
            авто{" "}
            <input
              type="number"
              step="0.001"
              value={factors.road}
              onChange={(e) => setFactors({ ...factors, road: Number(e.target.value) })}
            />
          </label>{" "}
          <button type="submit" className="primaryAction">Сохранить коэффициенты</button>
        </form>
        {saved && <p className="successMessage">{saved}</p>}
      </section>

      <section>
        <h2>Фильтр</h2>
        <label className="fieldInline">
          Груз{" "}
        <select value={shipmentId} onChange={(e) => setShipmentId(e.target.value)}>
          <option value="">Все грузы</option>
          {shipments.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id}
            </option>
          ))}
        </select>
        </label>
      </section>

      <section>
        <h2>Сводка</h2>
        <ul className="statsList">
          <li>Общий углеродный след (все участки маршрутов): {formatKgCo2(data.total)}</li>
          <li>Грузов в расчёте: {data.shipmentCount}</li>
          <li>
            По видам транспорта:{" "}
            {Object.entries(data.byTransport)
              .map(([k, v]) => `${transportLabel[k] ?? k}: ${formatKgCo2(v)}`)
              .join("; ")}
          </li>
        </ul>
      </section>

      {shipmentId && comparison.length > 0 && (
        <section>
          <h2>Сравнение маршрутов для {shipmentId}</h2>
          <p className="muted">Только выполнимые варианты. «Оставшийся путь» — незавершённые участки от текущей позиции груза.</p>
          <table className="stackedTable">
            <thead>
              <tr>
                <th>Маршрут</th>
                <th>Текущий</th>
                <th>CO₂ оставшегося пути</th>
                <th>CO₂ всего маршрута</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((c) => (
                <tr key={c.name}>
                  <td data-label="Маршрут">{c.name}</td>
                  <td data-label="Текущий">{c.current ? "да" : "—"}</td>
                  <td data-label="Оставшийся путь">{formatKgCo2(c.carbonFootprint)}</td>
                  <td data-label="Весь маршрут">
                    {c.fullCarbonFootprint != null ? formatKgCo2(c.fullCarbonFootprint) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h2>По этапам</h2>
        <table className="stackedTable">
          <thead>
            <tr>
              <th>Груз</th>
              <th>Маршрут</th>
              <th>Участок</th>
              <th>Транспорт</th>
              <th>Расстояние</th>
              <th>CO₂</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i}>
                <td data-label="Груз">{row.shipmentId}</td>
                <td data-label="Маршрут">{row.routeName}</td>
                <td data-label="Участок">
                  {row.from} → {row.to}
                </td>
                <td data-label="Транспорт">{transportLabel[row.transportType] ?? row.transportType}</td>
                <td data-label="Расстояние">{formatNumber(row.distance)} км</td>
                <td data-label="CO₂">{formatKgCo2(row.co2Emission)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default function EcologyPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <EcologyInner />
    </Suspense>
  );
}
