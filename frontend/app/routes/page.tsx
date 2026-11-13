"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { formatDateTime, formatHours, formatKgCo2, formatNumber, formatRub, signed } from "@/lib/format";
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
  destination: string;
  sequence: string[];
  distance: number;
  durationHours: number;
  cost: number;
  probability: number;
  riskLevel: string;
  estimatedDelay: number;
  stageCount: number;
  openStageCount?: number;
  carbonFootprint: number;
  recommendation: string;
  selectable: boolean;
  reasons: string[];
  scopeLabel?: string;
  switchNode?: string;
  switchEta?: string;
  switchNote?: string;
  connectorNote?: string;
  predictedArrival?: string;
  unavailableReason?: string;
  fullDistance?: number;
  fullCarbonFootprint?: number;
  stateVersion: string;
  historyMode?: string;
  historyMatchCount?: number;
  portRestriction?: { blocked?: boolean; delayed?: boolean; etaUnknown?: boolean; reason?: string };
  portRestrictionDelayed?: boolean;
  stages: Array<{ id: string; location: string; nextLocation: string; transportType: string; status: string }>;
};

type CatalogSortKey =
  | "name"
  | "origin"
  | "destination"
  | "transport"
  | "stageCount"
  | "distance"
  | "durationHours"
  | "cost"
  | "probability"
  | "carbonPerTon";

function transportSequenceLabel(row: CatalogRow): string {
  return row.sequence.map((mode) => transportLabel[mode] ?? mode).join(" + ");
}

function catalogSortValue(row: CatalogRow, key: CatalogSortKey): string | number {
  if (key === "transport") return transportSequenceLabel(row);
  return row[key];
}

function SortableTh({
  label,
  sortKey,
  active,
  direction,
  onSort,
}: {
  label: string;
  sortKey: CatalogSortKey;
  active: boolean;
  direction: "asc" | "desc";
  onSort: (key: CatalogSortKey) => void;
}) {
  return (
    <th scope="col" aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className="tableSortBtn" onClick={() => onSort(sortKey)}>
        {label}
        {active ? <span aria-hidden="true">{direction === "asc" ? " ↑" : " ↓"}</span> : null}
      </button>
    </th>
  );
}

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
    apiGet<CatalogRow[]>("/routes")
      .then(setCatalog)
      .catch((e) => setError(String((e as Error).message || e)));
    apiGet<Array<{ id: string; name: string }>>("/shipments")
      .then((rows) => setShipments(rows.map((r) => ({ id: r.id, name: r.name }))))
      .catch((e) => setError(String((e as Error).message || e)));
  }, []);

  const [loading, setLoading] = useState(false);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [catalogSort, setCatalogSort] = useState<{ key: CatalogSortKey; dir: "asc" | "desc" } | null>(null);
  const shipmentIdRef = useRef(shipmentId);
  const optionsRequest = useRef(0);
  const actionEpoch = useRef(0);
  shipmentIdRef.current = shipmentId;

  const sortedCatalog = useMemo(() => {
    if (!catalogSort) return catalog;
    const mult = catalogSort.dir === "asc" ? 1 : -1;
    return [...catalog].sort((a, b) => {
      const left = catalogSortValue(a, catalogSort.key);
      const right = catalogSortValue(b, catalogSort.key);
      if (typeof left === "number" && typeof right === "number") return (left - right) * mult;
      return String(left).localeCompare(String(right), "ru") * mult;
    });
  }, [catalog, catalogSort]);

  function toggleCatalogSort(key: CatalogSortKey) {
    setCatalogSort((prev) => {
      if (prev?.key === key) return { key, dir: prev.dir === "asc" ? "desc" : "asc" };
      return { key, dir: "asc" };
    });
  }

  function loadOptions(id: string) {
    const requestId = ++optionsRequest.current;
    const epoch = actionEpoch.current;
    setLoading(true);
    setError("");
    setStale(false);
    setOptions([]);
    apiGet<Option[]>(`/routes/options/${encodeURIComponent(id)}`)
      .then((rows) => {
        if (requestId !== optionsRequest.current || epoch !== actionEpoch.current) return;
        setOptions(rows);
      })
      .catch((e) => {
        if (requestId !== optionsRequest.current || epoch !== actionEpoch.current) return;
        setOptions([]);
        setError(String((e as Error).message || e));
      })
      .finally(() => {
        if (requestId !== optionsRequest.current || epoch !== actionEpoch.current) return;
        setLoading(false);
      });
  }

  function chooseShipment(id: string) {
    if (id === shipmentIdRef.current) return;
    shipmentIdRef.current = id;
    actionEpoch.current += 1;
    optionsRequest.current += 1;
    setShipmentId(id);
    setOptions([]);
    setLoading(true);
    setError("");
    setMessage("");
    setStale(false);
    setBusy(null);
  }

  useEffect(() => {
    if (initialShipment === shipmentIdRef.current) return;
    shipmentIdRef.current = initialShipment;
    actionEpoch.current += 1;
    optionsRequest.current += 1;
    setShipmentId(initialShipment);
    setOptions([]);
    setLoading(true);
    setError("");
    setMessage("");
    setStale(false);
    setBusy(null);
  }, [initialShipment]);

  useEffect(() => {
    if (shipmentId) loadOptions(shipmentId);
  }, [shipmentId]);

  async function selectRoute(option: Option) {
    const id = shipmentIdRef.current;
    const epoch = actionEpoch.current;
    setError("");
    setMessage("");
    setBusy(option.templateId);
    try {
      await apiPost("/routes/select", {
        shipmentId: id,
        templateId: option.templateId,
        expectedVersion: option.stateVersion,
      });
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      setMessage(
        `Выбран маршрут «${option.name}». Пройденные и текущие участки сохранены, карточка груза, карта и прогноз пересчитаны.`
      );
      loadOptions(id);
    } catch (e) {
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      if (e instanceof ApiError && e.status === 409) {
        setStale(true);
      } else {
        setError(String((e as Error).message));
      }
    } finally {
      if (epoch === actionEpoch.current && shipmentIdRef.current === id) setBusy(null);
    }
  }

  const current = options.find((o) => o.current);
  const alts = options.filter((o) => !o.current);
  const available = alts.filter((o) => o.selectable);
  const unavailable = alts.filter((o) => !o.selectable);

  return (
    <div className="appPage">
      <h1>Маршруты</h1>
      {error && <p className="error">{error}</p>}
      {message && <p className="successMessage">{message}</p>}


      <section aria-labelledby="compare-title">
        <h2 id="compare-title">Сравнение для груза</h2>
        <label className="fieldInline">
          Груз{" "}
          <select value={shipmentId} onChange={(e) => chooseShipment(e.target.value)}>
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} — {s.name}
              </option>
            ))}
          </select>
        </label>

        {stale && (
          <div className="staleBanner" role="alert">
            <p>
              Пока вы сравнивали варианты, состояние груза изменилось (новое событие или пересчёт). Маршрут не
              изменён — обновите варианты и проверьте сравнение ещё раз.
            </p>
            <button type="button" className="primaryAction" onClick={() => loadOptions(shipmentId)}>
              Обновить варианты
            </button>
          </div>
        )}
        {loading && <p className="muted">Загружаем варианты…</p>}

        {!loading && current && (
          <>
            <p className="muted scopeNote">
              {current.scopeLabel}. Время — от текущего момента до прогнозного прибытия, стоимость — оценка по тарифу
              маршрута для незавершённых участков, CO₂ — по каждому незавершённому участку (масса × км × коэффициент).
              Время — МСК.
            </p>
            <h3>Текущий маршрут</h3>
            <div className="optionCard" data-current>
              <ComparisonTable row={current} />
            </div>
          </>
        )}

        {!loading && available.length > 0 && (
          <>
            <h3>Альтернативы</h3>
            {available.map((row) => (
              <AltRouteBlock
                key={row.templateId}
                row={row}
                current={current}
                busy={busy === row.templateId}
                disabled={busy !== null || stale || loading}
                onSelect={() => selectRoute(row)}
              />
            ))}
          </>
        )}
        {current && !loading && available.length === 0 && (
          <p className="emptyState">
            Для этого груза сейчас нет физически выполнимых альтернатив — причины указаны ниже. Текущий маршрут остаётся
            в силе.
          </p>
        )}
        {!loading && unavailable.length > 0 && (
          <details className="unavailableList">
            <summary>Недоступные варианты ({unavailable.length})</summary>
            <ul>
              {unavailable.map((row) => (
                <li key={row.templateId}>
                  <strong>{row.name}</strong>
                  <span className="muted">{row.unavailableReason ?? "Маршрут недоступен для выбора"}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <p>
          <Link className="button-link" href={`/shipments/${encodeURIComponent(shipmentId)}`}>
            Карточка груза
          </Link>
        </p>
      </section>

      <section>
        <h2>Каталог маршрутов между портами</h2>
        <p className="muted">Справочно: показатели всего пути по шаблону, без учёта положения конкретного груза.</p>
        <table className="stackedTable">
          <thead>
            <tr>
              <SortableTh
                label="Маршрут"
                sortKey="name"
                active={catalogSort?.key === "name"}
                direction={catalogSort?.key === "name" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Откуда"
                sortKey="origin"
                active={catalogSort?.key === "origin"}
                direction={catalogSort?.key === "origin" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Куда"
                sortKey="destination"
                active={catalogSort?.key === "destination"}
                direction={catalogSort?.key === "destination" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Транспорт"
                sortKey="transport"
                active={catalogSort?.key === "transport"}
                direction={catalogSort?.key === "transport" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Этапов"
                sortKey="stageCount"
                active={catalogSort?.key === "stageCount"}
                direction={catalogSort?.key === "stageCount" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Расстояние"
                sortKey="distance"
                active={catalogSort?.key === "distance"}
                direction={catalogSort?.key === "distance" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Часы"
                sortKey="durationHours"
                active={catalogSort?.key === "durationHours"}
                direction={catalogSort?.key === "durationHours" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Стоимость"
                sortKey="cost"
                active={catalogSort?.key === "cost"}
                direction={catalogSort?.key === "cost" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="Риск"
                sortKey="probability"
                active={catalogSort?.key === "probability"}
                direction={catalogSort?.key === "probability" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
              <SortableTh
                label="CO₂/т"
                sortKey="carbonPerTon"
                active={catalogSort?.key === "carbonPerTon"}
                direction={catalogSort?.key === "carbonPerTon" ? catalogSort.dir : "asc"}
                onSort={toggleCatalogSort}
              />
            </tr>
          </thead>
          <tbody>
            {sortedCatalog.map((row) => (
              <tr key={row.templateId}>
                <td data-label="Маршрут">{row.name}</td>
                <td data-label="Откуда">{row.origin}</td>
                <td data-label="Куда">{row.destination}</td>
                <td data-label="Транспорт">{transportSequenceLabel(row)}</td>
                <td data-label="Этапов">{row.stageCount}</td>
                <td data-label="Расстояние">{formatNumber(row.distance)} км</td>
                <td data-label="Время">{row.durationHours} ч</td>
                <td data-label="Стоимость">{formatRub(row.cost)}</td>
                <td data-label="Риск">
                  {row.probability}% ({riskLabel[row.riskLevel]})
                </td>
                <td data-label="CO₂/т">{row.carbonPerTon} кг</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function pathLabel(row: Option) {
  const open = row.stages.filter((stage) => stage.status !== "completed");
  if (!open.length) return "—";
  return [open[0].location, ...open.map((stage) => stage.nextLocation)].join(" → ");
}

function ComparisonTable({ row }: { row: Option }) {
  return (
    <table className="comparisonTable">
      <caption>{row.name}</caption>
      <tbody>
        <tr>
          <th scope="row">Оставшийся путь</th>
          <td>{pathLabel(row)}</td>
        </tr>
        {!row.current && row.switchNode ? (
          <tr>
            <th scope="row">Где меняется маршрут</th>
            <td>
              {row.switchNode}
              {row.switchEta ? ` · ожидается ${formatDateTime(row.switchEta, true)}` : ""}
              {row.switchNote ? <div className="muted">{row.switchNote}</div> : null}
            </td>
          </tr>
        ) : null}
        {row.portRestriction?.reason ? (
          <tr>
            <th scope="row">Ограничение порта</th>
            <td>
              <strong className="staleBanner">{row.portRestriction.blocked ? "Отправление заблокировано" : "Задержка отправления"}</strong>
              <div className="muted">{row.portRestriction.reason}</div>
            </td>
          </tr>
        ) : null}
        <tr>
          <th scope="row">Прибытие (прогноз)</th>
          <td>
            <strong>{row.portRestriction?.etaUnknown || !row.predictedArrival ? "ETA не определён" : formatDateTime(row.predictedArrival, true)}</strong>
            {!row.portRestriction?.etaUnknown && row.predictedArrival && row.estimatedDelay != null ? (
              <span className="muted"> · задержка к контрактному сроку {formatHours(row.estimatedDelay)}</span>
            ) : null}
          </td>
        </tr>
        <tr>
          <th scope="row">Время до прибытия</th>
          <td>{formatHours(row.durationHours)}</td>
        </tr>
        <tr>
          <th scope="row">Расстояние</th>
          <td>
            {formatNumber(row.distance)} км
            <span className="muted"> · незавершённых участков {row.openStageCount ?? row.stageCount}</span>
          </td>
        </tr>
        <tr>
          <th scope="row">Стоимость (оценка)</th>
          <td>{formatRub(row.cost)}</td>
        </tr>
        <tr>
          <th scope="row">CO₂ оставшегося пути</th>
          <td>
            {formatKgCo2(row.carbonFootprint)}
            {row.fullCarbonFootprint != null ? (
              <span className="muted"> · весь маршрут {formatKgCo2(row.fullCarbonFootprint)}</span>
            ) : null}
          </td>
        </tr>
        <tr>
          <th scope="row">Риск сорвать стыковку</th>
          <td>
            {row.probability}% ({riskLabel[row.riskLevel] ?? row.riskLevel})
            {row.historyMode === "history_blend" ? (
              <span className="muted"> · учтено похожих рейсов: {row.historyMatchCount}</span>
            ) : null}
          </td>
        </tr>
        {row.connectorNote ? (
          <tr>
            <th scope="row">Стыковка</th>
            <td>{row.connectorNote}</td>
          </tr>
        ) : null}
        <tr>
          <th scope="row">Рекомендация</th>
          <td>{row.recommendation}</td>
        </tr>
      </tbody>
    </table>
  );
}

function AltRouteBlock({
  row,
  current,
  busy,
  disabled,
  onSelect,
}: {
  row: Option;
  current?: Option;
  busy: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <div className="optionCard">
      <ComparisonTable row={row} />
      {current && (
        <ul className="deltaList" aria-label="Разница с текущим маршрутом">
          <li>Прибытие: {signed(row.durationHours - current.durationHours, formatHours)}</li>
          <li>Стоимость: {signed(row.cost - current.cost, formatRub)}</li>
          <li>CO₂: {signed(row.carbonFootprint - current.carbonFootprint, formatKgCo2)}</li>
          <li>Риск: {signed(row.probability - current.probability, (v) => `${formatNumber(v)} п.п.`)}</li>
        </ul>
      )}
      <button type="button" className="primaryAction" onClick={onSelect} disabled={disabled}>
        {busy ? "Применяем…" : "Выбрать маршрут"}
      </button>
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
