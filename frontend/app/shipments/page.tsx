"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel, statusLabel, transportLabel } from "@/lib/labels";

type Shipment = {
  id: string;
  name: string;
  category: string;
  weight: number;
  containerCount: number;
  sender: string;
  receiver: string;
  origin: string;
  destination: string;
  currentTransport: string;
  status: string;
  plannedDeparture: string;
  plannedArrival: string;
  predictedArrival: string;
  riskLevel: string;
  probability: number;
};

type Meta = {
  ports: Array<{ name: string }>;
  sequences: Array<{ id: string; value: string[]; label: string }>;
};

export default function ShipmentsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Shipment[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [transport, setTransport] = useState("");
  const [deliveryBefore, setDeliveryBefore] = useState("");

  const [form, setForm] = useState({
    name: "",
    category: "",
    weight: "100",
    containerCount: "1",
    sender: "",
    receiver: "",
    origin: "Махачкала",
    destination: "Энзели",
    plannedDeparture: "2026-11-14T08:00:00",
    plannedArrival: "2026-11-18T18:00:00",
    transportSequence: "road,sea",
    notes: "",
  });

  function reload() {
    apiGet<Shipment[]>("/shipments")
      .then(setRows)
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    reload();
    apiGet<Meta>("/meta").then(setMeta);
  }, []);

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (search && !`${row.id} ${row.name}`.toLowerCase().includes(search.toLowerCase())) return false;
      if (status && row.status !== status) return false;
      if (risk && row.riskLevel !== risk) return false;
      if (origin && row.origin !== origin) return false;
      if (destination && row.destination !== destination) return false;
      if (transport && row.currentTransport !== transport) return false;
      if (deliveryBefore && row.plannedArrival > deliveryBefore) return false;
      return true;
    });
  }, [rows, search, status, risk, origin, destination, transport, deliveryBefore]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    const seq = meta?.sequences.find((s) => s.id === form.transportSequence)?.value ?? ["road", "sea"];
    try {
      const detail = await apiPost<{ shipment: { id: string } }>("/shipments", {
        ...form,
        weight: Number(form.weight),
        containerCount: Number(form.containerCount),
        transportSequence: seq,
      });
      setShowForm(false);
      reload();
      router.push(`/shipments/${detail.shipment.id}`);
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  return (
    <>
      <h1>Грузы</h1>
      {error && <p className="error">{error}</p>}
      <button type="button" onClick={() => setShowForm((v) => !v)}>
        {showForm ? "Скрыть форму" : "Добавить груз"}
      </button>

      {showForm && meta && (
        <form onSubmit={onCreate} style={{ marginTop: 12, maxWidth: 480 }}>
          <p>
            <label>
              Название
              <br />
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
          </p>
          <p>
            <label>
              Категория
              <br />
              <input required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </label>
          </p>
          <p>
            <label>
              Вес (т)
              <br />
              <input required type="number" value={form.weight} onChange={(e) => setForm({ ...form, weight: e.target.value })} />
            </label>
          </p>
          <p>
            <label>
              Контейнеры
              <br />
              <input
                required
                type="number"
                value={form.containerCount}
                onChange={(e) => setForm({ ...form, containerCount: e.target.value })}
              />
            </label>
          </p>
          <p>
            <label>
              Отправитель
              <br />
              <input required value={form.sender} onChange={(e) => setForm({ ...form, sender: e.target.value })} />
            </label>
          </p>
          <p>
            <label>
              Получатель
              <br />
              <input required value={form.receiver} onChange={(e) => setForm({ ...form, receiver: e.target.value })} />
            </label>
          </p>
          <p>
            <label>
              Пункт отправления
              <br />
              <select value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}>
                {meta.ports.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <p>
            <label>
              Пункт назначения
              <br />
              <select value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}>
                {meta.ports.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <p>
            <label>
              Дата отправления
              <br />
              <input
                required
                value={form.plannedDeparture}
                onChange={(e) => setForm({ ...form, plannedDeparture: e.target.value })}
              />
            </label>
          </p>
          <p>
            <label>
              Плановая доставка
              <br />
              <input
                required
                value={form.plannedArrival}
                onChange={(e) => setForm({ ...form, plannedArrival: e.target.value })}
              />
            </label>
          </p>
          <p>
            <label>
              Транспорт
              <br />
              <select
                value={form.transportSequence}
                onChange={(e) => setForm({ ...form, transportSequence: e.target.value })}
              >
                {meta.sequences.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <p>
            <label>
              Примечание
              <br />
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </label>
          </p>
          <button type="submit">Сохранить груз</button>
        </form>
      )}

      <section style={{ marginTop: 16 }}>
        <h2>Фильтры</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <input placeholder="Поиск по номеру или названию" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(statusLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="">Все риски</option>
            <option value="low">низкий</option>
            <option value="medium">средний</option>
            <option value="high">высокий</option>
            <option value="none">—</option>
          </select>
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
            <option value="">Любой откуда</option>
            {meta?.ports.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">Любой куда</option>
            {meta?.ports.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={transport} onChange={(e) => setTransport(e.target.value)}>
            <option value="">Любой транспорт</option>
            {Object.entries(transportLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <input
            placeholder="Доставка до (ISO дата)"
            value={deliveryBefore}
            onChange={(e) => setDeliveryBefore(e.target.value)}
          />
        </div>
      </section>

      <section>
        <h2>Список ({filtered.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Номер</th>
              <th>Название</th>
              <th>Категория</th>
              <th>Вес</th>
              <th>Конт.</th>
              <th>Отправитель</th>
              <th>Получатель</th>
              <th>Откуда</th>
              <th>Куда</th>
              <th>Транспорт</th>
              <th>Статус</th>
              <th>Отправление</th>
              <th>План</th>
              <th>Прогноз</th>
              <th>Риск</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/shipments/${row.id}`}>{row.id}</Link>
                </td>
                <td>{row.name}</td>
                <td>{row.category}</td>
                <td>{row.weight}</td>
                <td>{row.containerCount}</td>
                <td>{row.sender}</td>
                <td>{row.receiver}</td>
                <td>{row.origin}</td>
                <td>{row.destination}</td>
                <td>{transportLabel[row.currentTransport] ?? row.currentTransport}</td>
                <td>{statusLabel[row.status] ?? row.status}</td>
                <td>{row.plannedDeparture}</td>
                <td>{row.plannedArrival}</td>
                <td>{row.predictedArrival}</td>
                <td>
                  {riskLabel[row.riskLevel] ?? row.riskLevel} ({row.probability}%)
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
