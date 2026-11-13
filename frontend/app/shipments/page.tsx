"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ShipmentCard } from "@/components/shipments/ShipmentCard";
import { ShipmentListRows } from "@/components/shipments/ShipmentListRows";
import { ViewToggle } from "@/components/shipments/ViewToggle";
import cardStyles from "@/components/shipments/shipmentCards.module.css";
import { useShipmentCardNavigation } from "@/hooks/useShipmentCardNavigation";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel, statusLabel, transportLabel } from "@/lib/labels";
import { toShipmentCardData } from "@/lib/shipments/adapters";
import { defaultListPrefs, loadListPrefs, saveListPrefs, type ShipmentListPrefs } from "@/lib/shipments/listStorage";

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
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [prefs, setPrefs] = useState<ShipmentListPrefs>(defaultListPrefs);
  const [prefsReady, setPrefsReady] = useState(false);

  const { openCard, returningId } = useShipmentCardNavigation("/shipments", prefsReady && !loading, prefs);

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

  useEffect(() => {
    setPrefs(loadListPrefs());
    setPrefsReady(true);
  }, []);

  useEffect(() => {
    if (prefsReady) saveListPrefs(prefs);
  }, [prefs, prefsReady]);

  function reload() {
    setLoading(true);
    apiGet<Shipment[]>("/shipments")
      .then(setRows)
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    apiGet<Meta>("/meta").then(setMeta);
  }, []);

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (prefs.search && !`${row.id} ${row.name}`.toLowerCase().includes(prefs.search.toLowerCase())) return false;
      if (prefs.status && row.status !== prefs.status) return false;
      if (prefs.risk && row.riskLevel !== prefs.risk) return false;
      if (prefs.origin && row.origin !== prefs.origin) return false;
      if (prefs.destination && row.destination !== prefs.destination) return false;
      if (prefs.transport && row.currentTransport !== prefs.transport) return false;
      if (prefs.deliveryBefore && row.plannedArrival > prefs.deliveryBefore) return false;
      return true;
    });
  }, [rows, prefs]);

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

  function setPref<K extends keyof ShipmentListPrefs>(key: K, value: ShipmentListPrefs[K]) {
    setPrefs((current) => ({ ...current, [key]: value }));
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
        <div className={cardStyles.filtersRow}>
          <input
            placeholder="Поиск по номеру или названию"
            value={prefs.search}
            onChange={(e) => setPref("search", e.target.value)}
          />
          <select value={prefs.status} onChange={(e) => setPref("status", e.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(statusLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select value={prefs.risk} onChange={(e) => setPref("risk", e.target.value)}>
            <option value="">Все риски</option>
            <option value="low">низкий</option>
            <option value="medium">средний</option>
            <option value="high">высокий</option>
            <option value="none">—</option>
          </select>
          <select value={prefs.origin} onChange={(e) => setPref("origin", e.target.value)}>
            <option value="">Любой откуда</option>
            {meta?.ports.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={prefs.destination} onChange={(e) => setPref("destination", e.target.value)}>
            <option value="">Любой куда</option>
            {meta?.ports.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={prefs.transport} onChange={(e) => setPref("transport", e.target.value)}>
            <option value="">Любой транспорт</option>
            {Object.entries(transportLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <input
            placeholder="Доставка до (ISO дата)"
            value={prefs.deliveryBefore}
            onChange={(e) => setPref("deliveryBefore", e.target.value)}
          />
        </div>
      </section>

      <section id="list-view">
        <div className={cardStyles.sectionHead}>
          <h2>
            Список{" "}
            <span className={cardStyles.sectionHeadMeta} aria-live="polite">
              {loading ? "…" : `· ${filtered.length}`}
            </span>
          </h2>
          <ViewToggle value={prefs.view} onChange={(view) => setPref("view", view)} />
        </div>
        {loading && <p role="status">Загрузка грузов…</p>}
        {!loading && filtered.length === 0 && (
          <p className={cardStyles.emptyState}>
            {rows.length === 0 ? "Грузов пока нет." : "По выбранным фильтрам ничего не найдено."}
          </p>
        )}
        {!loading && filtered.length > 0 && prefs.view === "cards" && (
          <div className={cardStyles.cardGrid}>
            {filtered.map((row) => {
              const item = toShipmentCardData(row);
              const href = `/shipments/${encodeURIComponent(item.id)}`;
              return (
                <ShipmentCard
                  key={item.id}
                  item={item}
                  href={href}
                  eagerMap={returningId === item.id}
                  onActivate={openCard}
                />
              );
            })}
          </div>
        )}
        {!loading && filtered.length > 0 && prefs.view === "list" && (
          <ShipmentListRows
            items={filtered.map(toShipmentCardData)}
            hrefFor={(id) => `/shipments/${encodeURIComponent(id)}`}
            onActivate={openCard}
          />
        )}
      </section>
    </>
  );
}
