"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { riskLabel, statusLabel } from "@/lib/labels";

type MapData = {
  places: Array<{ name: string; x: number; y: number; kind: string; waitingShipments?: number; weather?: string }>;
  shipments: Array<{
    id: string;
    name: string;
    status: string;
    riskLevel: string;
    position: { x: number; y: number; name: string };
    stages: Array<Record<string, unknown>>;
  }>;
};

type StageInfo = {
  title: string;
  lines: string[];
};

export default function MapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [filter, setFilter] = useState<"all" | "in_transit" | "risk" | "delayed">("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [stageInfo, setStageInfo] = useState<StageInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<MapData>("/map")
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
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

  const selectedShipment = filtered.find((s) => s.id === selected) ?? filtered[0];

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Загрузка…</p>;

  return (
    <>
      <h1>Карта перевозок</h1>
      <p className="muted">Схематическая карта коридора (демо). Координаты портов и положения грузов из общей базы.</p>

      <div style={{ marginBottom: 8 }}>
        <label>
          Фильтр:{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
            <option value="all">Все грузы</option>
            <option value="in_transit">В пути</option>
            <option value="risk">С риском</option>
            <option value="delayed">Задержанные</option>
          </select>
        </label>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <svg viewBox="0 0 100 100" width={520} height={400} style={{ border: "1px solid #ccc" }}>
          {data.places.map((place) => (
            <g
              key={place.name}
              onClick={() =>
                setStageInfo({
                  title: place.name,
                  lines: [
                    `Тип: ${place.kind === "port" ? "порт" : "узел"}`,
                    `Ожидающих грузов: ${place.waitingShipments ?? 0}`,
                    place.weather ? `Погода: ${place.weather}` : "",
                  ].filter(Boolean),
                })
              }
              style={{ cursor: "pointer" }}
            >
              <circle cx={place.x} cy={place.y} r={place.kind === "port" ? 3.5 : 2} fill={place.kind === "port" ? "#333" : "#999"} />
              <text x={place.x + 2} y={place.y - 2} fontSize="3">
                {place.name}
              </text>
            </g>
          ))}

          {selectedShipment?.stages.map((stage, i) => {
            const from = data.places.find((p) => p.name === stage.location);
            const to = data.places.find((p) => p.name === stage.nextLocation);
            if (!from || !to) return null;
            return (
              <line
                key={i}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="#666"
                strokeWidth={selected ? 0.6 : 0.3}
                strokeDasharray={String(stage.status) === "completed" ? "" : "2,1"}
              />
            );
          })}

          {filtered.map((s) => (
            <g key={s.id} onClick={() => setSelected(s.id)} style={{ cursor: "pointer" }}>
              <rect
                x={s.position.x - 1.5}
                y={s.position.y - 1.5}
                width={3}
                height={3}
                fill={s.id === selectedShipment?.id ? "#000" : "#666"}
              />
              <title>
                {s.id} {s.name}
              </title>
            </g>
          ))}
        </svg>

        <div style={{ flex: 1, minWidth: 240 }}>
          <h2>Грузы на карте</h2>
          <ul>
            {filtered.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => setSelected(s.id)} style={{ border: "none", background: "none", padding: 0 }}>
                  {s.id}
                </button>{" "}
                — {statusLabel[s.status] ?? s.status}, риск {riskLabel[s.riskLevel]}
                {selected === s.id && (
                  <>
                    {" "}
                    <Link href={`/shipments/${s.id}`}>карточка</Link>
                  </>
                )}
              </li>
            ))}
          </ul>

          {selectedShipment && (
            <section>
              <h2>Маршрут {selectedShipment.id}</h2>
              <table>
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Прибытие</th>
                    <th>Транспорт</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedShipment.stages.map((st) => (
                    <tr
                      key={String(st.id)}
                      onClick={() =>
                        setStageInfo({
                          title: `${String(st.location)} → ${String(st.nextLocation)}`,
                          lines: [
                            `План: ${String(st.plannedArrival)}`,
                            `Статус: ${String(st.status)}`,
                            `Описание: ${String(st.description)}`,
                          ],
                        })
                      }
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        {String(st.location)} → {String(st.nextLocation)}
                      </td>
                      <td>{String(st.plannedArrival)}</td>
                      <td>{String(st.transportType)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {stageInfo && (
            <section>
              <h2>{stageInfo.title}</h2>
              <ul>
                {stageInfo.lines.map((line, i) => (
                  <li key={i}>
                    {line}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
