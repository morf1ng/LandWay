"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { docStatusLabel, riskLabel, statusLabel, transportLabel } from "@/lib/labels";

type Detail = {
  shipment: Record<string, unknown>;
  route: { stages: Array<Record<string, unknown>>; name: string };
  prediction: Record<string, unknown>;
  documents: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  carbon: { total: number; stages: Array<Record<string, unknown>> };
};

export default function ShipmentDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(false);
  const [notes, setNotes] = useState("");

  function load() {
    apiGet<Detail>(`/shipments/${id}`)
      .then((d) => {
        setData(d);
        setNotes(String(d.shipment.notes ?? ""));
      })
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    load();
  }, [id]);

  async function saveNotes() {
    try {
      await apiPatch(`/shipments/${id}`, { notes });
      setEdit(false);
      load();
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Загрузка…</p>;

  const s = data.shipment;
  const p = data.prediction;

  return (
    <>
      <p>
        <Link href="/shipments">← К списку грузов</Link>
      </p>
      <h1>
        {String(s.id)} — {String(s.name)}
      </h1>

      <section>
        <h2>Общая информация</h2>
        <ul>
          <li>Статус: {statusLabel[String(s.status)] ?? String(s.status)}</li>
          <li>Отправитель: {String(s.sender)}</li>
          <li>Получатель: {String(s.receiver)}</li>
          <li>Вес: {String(s.weight)} т</li>
          <li>Контейнеров: {String(s.containerCount)}</li>
          <li>Текущее место: {String(s.currentLocation)}</li>
        </ul>
      </section>

      <section>
        <h2>Маршрут</h2>
        <p>
          {String(s.origin)} → {String(s.destination)} ({data.route.name})
        </p>
        <ol>
          {data.route.stages.map((stage) => (
            <li key={String(stage.id)}>
              {String(stage.location)} → {String(stage.nextLocation)} ({transportLabel[String(stage.transportType)]})
            </li>
          ))}
        </ol>
        <p>
          <Link className="button-link" href={`/routes?shipment=${id}`}>
            Посмотреть маршрут
          </Link>{" "}
          <Link className="button-link" href={`/analytics?shipment=${id}`}>
            Открыть прогноз
          </Link>{" "}
          <Link className="button-link" href={`/customs?shipment=${id}`}>
            Документы
          </Link>
        </p>
      </section>

      <section>
        <h2>История перемещения</h2>
        <table>
          <thead>
            <tr>
              <th>Время</th>
              <th>Место</th>
              <th>Транспорт</th>
              <th>Событие</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {data.history.map((ev, i) => (
              <tr key={i}>
                <td>{String(ev.time)}</td>
                <td>{String(ev.location)}</td>
                <td>{transportLabel[String(ev.transport)] ?? String(ev.transport)}</td>
                <td>{String(ev.description)}</td>
                <td>{String(ev.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Сроки</h2>
        <ul>
          <li>Плановая доставка: {String(s.plannedArrival)}</li>
          <li>Прогноз: {String(s.predictedArrival)}</li>
          <li>Задержка (ч): {String(p.estimatedDelay)}</li>
        </ul>
      </section>

      <section>
        <h2>Риски</h2>
        <p>
          {riskLabel[String(p.riskLevel)] ?? String(p.riskLevel)} — {String(p.probability)}%
        </p>
        <ul>
          {(p.reasons as string[]).map((r, i) => (
            <li key={i}>
              {r}
            </li>
          ))}
        </ul>
        <p>Рекомендация: {String(p.recommendation)}</p>
      </section>

      <section>
        <h2>Документы</h2>
        <ul>
          {data.documents.map((d) => (
            <li key={String(d.id)}>
              {String(d.name)} — {docStatusLabel[String(d.status)] ?? String(d.status)}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Экологические показатели</h2>
        <p>Углеродный след: {data.carbon.total} кг CO₂ (демонстрационный расчёт)</p>
        <ul>
          {data.carbon.stages.map((row, i) => (
            <li key={i}>
              {String(row.from)} → {String(row.to)}: {String(row.co2Emission)} кг
            </li>
          ))}
        </ul>
        <Link className="button-link" href={`/ecology?shipment=${id}`}>
          Подробнее в экологии
        </Link>
      </section>

      <section>
        <h2>Редактирование</h2>
        {!edit ? (
          <button type="button" onClick={() => setEdit(true)}>
            Редактировать груз
          </button>
        ) : (
          <div>
            <label>
              Дополнительная информация
              <br />
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} style={{ width: "100%" }} />
            </label>
            <br />
            <button type="button" onClick={saveNotes}>
              Сохранить
            </button>{" "}
            <button type="button" onClick={() => setEdit(false)}>
              Отмена
            </button>
          </div>
        )}
        {String(s.notes) && !edit && <p className="muted">{String(s.notes)}</p>}
      </section>
    </>
  );
}
