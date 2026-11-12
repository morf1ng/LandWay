"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel, transportLabel } from "@/lib/labels";

type CatalogRow = {
  templateId: string;
  name: string;
  origin: string;
  destination: string;
  sequence: string[];
  stageCount: number;
  distance: number;
  durationHours: number;
  cost: number;
  probability: number;
  riskLevel: string;
  carbonPerTon: number;
};

type Option = {
  templateId: string;
  name: string;
  current: boolean;
  durationHours: number;
  cost: number;
  probability: number;
  riskLevel: string;
  estimatedDelay: number;
  stageCount: number;
  carbonFootprint: number;
  recommendation: string;
  selectable: boolean;
  reasons: string[];
};

function RoutesInner() {
  const search = useSearchParams();
  const initialShipment = search.get("shipment") ?? "SCT-1001";
  const [catalog, setCatalog] = useState<CatalogRow[]>([]);
  const [shipmentId, setShipmentId] = useState(initialShipment);
  const [shipments, setShipments] = useState<Array<{ id: string; name: string }>>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<CatalogRow[]>("/routes").then(setCatalog);
    apiGet<Array<{ id: string; name: string }>>("/shipments").then((rows) =>
      setShipments(rows.map((r) => ({ id: r.id, name: r.name })))
    );
  }, []);

  useEffect(() => {
    setShipmentId(initialShipment);
  }, [initialShipment]);

  function loadOptions(id: string) {
    apiGet<Option[]>(`/routes/options/${id}`)
      .then(setOptions)
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    if (shipmentId) loadOptions(shipmentId);
  }, [shipmentId]);

  async function selectRoute(templateId: string) {
    setError("");
    setMessage("");
    try {
      await apiPost("/routes/select", { shipmentId, templateId });
      setMessage("Маршрут обновлён. Карточка груза, карта и прогноз пересчитаны.");
      loadOptions(shipmentId);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  const current = options.find((o) => o.current);
  const alts = options.filter((o) => !o.current);

  return (
    <div className="appPage">
      <h1>Маршруты</h1>
      {error && <p className="error">{error}</p>}
      {message && <p className="successMessage">{message}</p>}

      <section>
        <h2>Каталог маршрутов между портами</h2>
        <table className="stackedTable">
          <thead>
            <tr>
              <th>Маршрут</th>
              <th>Откуда</th>
              <th>Куда</th>
              <th>Транспорт</th>
              <th>Этапов</th>
              <th>Расстояние</th>
              <th>Часы</th>
              <th>Стоимость</th>
              <th>Риск</th>
              <th>CO₂/т</th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((row) => (
              <tr key={row.templateId}>
                <td data-label="Маршрут">{row.name}</td>
                <td data-label="Откуда">{row.origin}</td>
                <td data-label="Куда">{row.destination}</td>
                <td data-label="Транспорт">{row.sequence.map((mode) => transportLabel[mode] ?? mode).join(" + ")}</td>
                <td data-label="Этапов">{row.stageCount}</td>
                <td data-label="Расстояние">{row.distance.toLocaleString("ru-RU")} км</td>
                <td data-label="Время">{row.durationHours} ч</td>
                <td data-label="Стоимость">{row.cost.toLocaleString("ru-RU")} ₽</td>
                <td data-label="Риск">
                  {row.probability}% ({riskLabel[row.riskLevel]})
                </td>
                <td data-label="CO₂/т">{row.carbonPerTon} кг</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Сравнение для груза</h2>
        <label>
          Груз:{" "}
          <select value={shipmentId} onChange={(e) => setShipmentId(e.target.value)}>
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} — {s.name}
              </option>
            ))}
          </select>
        </label>

        {current && (
          <>
            <h3>Текущий маршрут</h3>
            <ComparisonTable row={current} />
          </>
        )}

        {alts.length > 0 && (
          <>
            <h3>Альтернативы</h3>
            {alts.map((row) => (
              <AltRouteBlock
                key={row.templateId}
                row={row}
                current={current}
                onSelect={() => selectRoute(row.templateId)}
              />
            ))}
          </>
        )}
        <p>
          <Link className="button-link" href={`/shipments/${shipmentId}`}>
            Карточка груза
          </Link>
        </p>
      </section>
    </div>
  );
}

function ComparisonTable({ row }: { row: Option }) {
  return (
    <table>
      <tbody>
        <tr>
          <th>Название</th>
          <td>{row.name}</td>
        </tr>
        <tr>
          <th>Длительность, ч</th>
          <td>{row.durationHours}</td>
        </tr>
        <tr>
          <th>Стоимость</th>
          <td>{row.cost.toLocaleString("ru-RU")} ₽</td>
        </tr>
        <tr>
          <th>Риск</th>
          <td>
            {row.probability}% ({riskLabel[row.riskLevel]})
          </td>
        </tr>
        <tr>
          <th>Задержка, ч</th>
          <td>{row.estimatedDelay}</td>
        </tr>
        <tr>
          <th>Этапов</th>
          <td>{row.stageCount}</td>
        </tr>
        <tr>
          <th>CO₂</th>
          <td>{row.carbonFootprint} кг</td>
        </tr>
        <tr>
          <th>Рекомендация</th>
          <td>{row.recommendation}</td>
        </tr>
      </tbody>
    </table>
  );
}

function AltRouteBlock({ row, current, onSelect }: { row: Option; current?: Option; onSelect: () => void }) {
  return (
    <div className="optionCard">
      <ComparisonTable row={row} />
      {current && (
        <p className="muted">
          Δ время: {(row.durationHours - current.durationHours).toFixed(1)} ч, Δ стоимость: {row.cost - current.cost},
          Δ риск: {row.probability - current.probability} п.п., Δ CO₂:{" "}
          {(row.carbonFootprint - current.carbonFootprint).toFixed(1)} кг
        </p>
      )}
      {row.selectable ? (
        <button type="button" className="primaryAction" onClick={onSelect}>
          Выбрать маршрут
        </button>
      ) : (
        <p className="muted">Маршрут недоступен для выбора</p>
      )}
    </div>
  );
}

export default function RoutesPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <RoutesInner />
    </Suspense>
  );
}
