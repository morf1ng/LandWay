"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { InfrastructureStatus } from "@/components/InfrastructureStatus";
import panelStyles from "@/components/map/map.module.css";
import { apiGet } from "@/lib/api";
import { riskLabel, statusLabel, transportLabel } from "@/lib/labels";
import { formatArrivalRu } from "@/lib/shipments/format";
import { formatHours } from "@/lib/format";

const stageStatusText: Record<string, string> = {
  completed: "пройден",
  in_progress: "в пути",
  delayed: "в пути с опозданием",
  pending: "впереди",
};

function expectedArrival(stage: Record<string, unknown>): string | null {
  if (stage.actualArrival) return String(stage.actualArrival);
  if (!stage.plannedArrival) return null;
  const planned = new Date(`${String(stage.plannedArrival)}+03:00`);
  if (Number.isNaN(planned.getTime())) return String(stage.plannedArrival);
  const shifted = new Date(planned.getTime() + Number(stage.delayHours ?? 0) * 3600_000);
  return shifted.toISOString();
}
import type { MapPlace, MapShipment } from "@/lib/map/geo";
import { loadLiveInfrastructure, type InfrastructureSnapshot } from "@/lib/infrastructure";

const CorridorMap = dynamic(() => import("@/components/map/CorridorMap").then((m) => m.CorridorMap), {
  ssr: false,
  loading: () => <p className="muted">Загрузка карты…</p>,
});

type MapData = {
  places: MapPlace[];
  shipments: MapShipment[];
  corridor?: {
    label: string;
    source: string;
    sourceName: string;
    note: string;
    nodes: Array<{ name: string; lat: number; lon: number; kind: string }>;
    segments: Array<{ from: string; to: string; mode: string }>;
  };
};

type StageInfo = {
  title: string;
  lines: string[];
};

export default function MapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [filter, setFilter] = useState<"all" | "in_transit" | "risk" | "delayed">("all");
  const [overview, setOverview] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [stageInfo, setStageInfo] = useState<StageInfo | null>(null);
  const [error, setError] = useState("");
  const [liveInfrastructure, setLiveInfrastructure] = useState<InfrastructureSnapshot | null>(null);
  const [liveError, setLiveError] = useState(false);

  useEffect(() => {
    apiGet<MapData>("/map")
      .then((payload) => {
        setData(payload);
        if (payload.shipments[0]) setSelected(payload.shipments[0].id);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    loadLiveInfrastructure()
      .then(setLiveInfrastructure)
      .catch(() => setLiveError(true));
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.shipments.filter((s) => {
      if (filter === "all") return true;
      if (filter === "in_transit") return s.status === "in_transit" || s.status === "delayed";
      if (filter === "risk") return s.riskLevel === "medium" || s.riskLevel === "high";
      if (filter === "delayed") return s.status === "delayed";
      return true;
    });
  }, [data, filter]);

  const selectedShipment = filtered.find((s) => s.id === selected) ?? filtered[0] ?? null;
  const places = useMemo(() => {
    if (!data) return [];
    const liveByName = new Map(liveInfrastructure?.ports.map((port) => [port.name, port]) ?? []);
    return data.places.map((place) => {
      const status = liveByName.get(place.name);
      return status ? { ...place, ...status, kind: place.kind, sourceKind: status.sourceKind ?? "live" } : place;
    });
  }, [data, liveInfrastructure]);

  useEffect(() => {
    if (!selectedShipment) return;
    if (!filtered.some((s) => s.id === selected)) setSelected(selectedShipment.id);
  }, [filtered, selected, selectedShipment]);

  if (error) {
    return (
      <div className={panelStyles.page}>
        <p className="error" role="alert">Не удалось загрузить карту: {error}</p>
        <button type="button" onClick={() => window.location.reload()}>Повторить</button>
      </div>
    );
  }
  if (!data) return <p aria-busy="true">Загрузка…</p>;

  return (
    <div className={panelStyles.page}>
      <h1>Карта перевозок</h1>
      <p className={panelStyles.lead}>Транскаспийская ветвь коридора от России до Индии. Линии обзора схематичны; положение грузов расчётное, не GPS.</p>

      <div className={panelStyles.toolbar}>
        <div className={panelStyles.mapMode} aria-label="Масштаб карты">
          <button type="button" aria-pressed={overview} onClick={() => setOverview(true)}>Весь коридор</button>
          <button type="button" aria-pressed={!overview} onClick={() => setOverview(false)}>Грузы на Каспии</button>
        </div>
        <label>
          Фильтр{" "}
          <select
            className={panelStyles.filterSelect}
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
          >
            <option value="all">Все грузы</option>
            <option value="in_transit">В пути</option>
            <option value="risk">С риском</option>
            <option value="delayed">Задержанные</option>
          </select>
        </label>
        <span className="muted">На карте: {filtered.length}</span>
      </div>

      <div className={panelStyles.layout}>
        <div className={panelStyles.mapCard}>
          <CorridorMap
            places={places}
            shipments={filtered}
            selectedId={selectedShipment?.id ?? null}
            onSelect={setSelected}
            corridor={data.corridor}
            overview={overview}
          />
          <div className={panelStyles.legend} aria-hidden="true">
            <span>
              <i style={{ background: "#4800ff" }} /> Порт
            </span>
            <span>
              <i style={{ background: "#8a8494" }} /> Узел
            </span>
            <span>
              <i style={{ background: "#4800ff", borderRadius: 2, transform: "rotate(45deg)" }} /> Груз
            </span>
            <span>Маршрут: ж/д · авто · море</span>
          </div>
          {data.corridor && <div className={panelStyles.sourceNote}>{data.corridor.note} Основа: <a href={data.corridor.source} target="_blank" rel="noopener noreferrer">{data.corridor.sourceName} ↗</a></div>}
        </div>

        <aside className={panelStyles.side}>
          <section className={panelStyles.panel}>
            <h2>Грузы на карте</h2>
            <ul className={panelStyles.shipmentList}>
              {filtered.map((s) => (
                <li key={s.id}>
                  <button type="button" data-active={s.id === selectedShipment?.id} onClick={() => setSelected(s.id)}>
                    <strong>
                      {s.id} · {s.origin} → {s.destination}
                    </strong>
                    <small>
                      {statusLabel[s.status] ?? s.status} · риск {riskLabel[s.riskLevel] ?? s.riskLevel}
                      {s.position?.name ? ` · расчётно: ${s.position.name}` : ""}
                    </small>
                  </button>
                </li>
              ))}
            </ul>
            {filtered.length === 0 && <p className={panelStyles.mutedNote}>По этому фильтру грузов нет.</p>}
            {selectedShipment && (
              <p className={panelStyles.mutedNote}>
                <Link href={`/shipments/${selectedShipment.id}`}>Открыть карточку {selectedShipment.id}</Link>
              </p>
            )}
          </section>

          {selectedShipment && (
            <InfrastructureStatus
              stages={selectedShipment.stages}
              ports={places.filter((place) => place.kind === "port")}
              railStatuses={liveInfrastructure?.rail}
            />
          )}
          {liveError && <p className={panelStyles.mutedNote}>Оперативный источник недоступен. Показаны только демоданные.</p>}

          {selectedShipment && (
            <section className={panelStyles.panel}>
              <h2>Маршрут {selectedShipment.id}</h2>
              <table className={panelStyles.stageTable}>
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Ожидаемое прибытие (МСК)</th>
                    <th>Транспорт</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedShipment.stages.map((st, idx) => {
                    const title = `${String(st.location)} → ${String(st.nextLocation)}`;
                    const active = stageInfo?.title === title;
                    const arrival = expectedArrival(st as Record<string, unknown>);
                    const delay = Number(st.delayHours ?? 0);
                    const statusText = stageStatusText[String(st.status)] ?? String(st.status);
                    return (
                      <tr key={String(st.id ?? idx)} data-active={active}>
                        <td>
                          <button
                            type="button"
                            className={panelStyles.stageButton}
                            aria-expanded={active}
                            onClick={() =>
                              setStageInfo(
                                active
                                  ? null
                                  : {
                                      title,
                                      lines: [
                                        `Статус: ${statusText}${delay > 0 ? `, опоздание ${formatHours(delay)}` : ""}`,
                                        st.plannedArrival ? `План: ${formatArrivalRu(String(st.plannedArrival))} МСК` : "",
                                        arrival ? `Ожидается: ${formatArrivalRu(arrival)} МСК` : "",
                                        st.description ? `Описание: ${String(st.description)}` : "",
                                      ].filter(Boolean),
                                    }
                              )
                            }
                          >
                            {title}
                          </button>
                          <small className="muted"> {statusText}</small>
                        </td>
                        <td>{arrival ? formatArrivalRu(arrival) : "—"}</td>
                        <td>{transportLabel[String(st.transportType)] ?? String(st.transportType)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {stageInfo && (
            <section className={panelStyles.panel}>
              <h2>{stageInfo.title}</h2>
              <ul>
                {stageInfo.lines.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
