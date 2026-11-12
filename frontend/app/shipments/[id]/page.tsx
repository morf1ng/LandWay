"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { RoutePreview } from "@/components/shipments/RoutePreview";
import { InfrastructureStatus } from "@/components/InfrastructureStatus";
import styles from "@/components/shipments/shipmentCards.module.css";
import { useShipmentDetailNavigation } from "@/hooks/useShipmentCardNavigation";
import { apiGet, apiPatch } from "@/lib/api";
import { docStatusLabel, riskLabel, statusLabel, transportLabel } from "@/lib/labels";
import { formatArrivalRu } from "@/lib/shipments/format";
import { readReturnHref } from "@/lib/shipments/listStorage";
import { loadLiveInfrastructure, type InfrastructurePort, type InfrastructureRailStatus } from "@/lib/infrastructure";

type Detail = {
  shipment: Record<string, unknown>;
  route: { stages: Array<Record<string, unknown>>; name: string };
  prediction: Record<string, unknown>;
  documents: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  carbon: { total: number; stages: Array<Record<string, unknown>> };
};

const eventStatusLabel: Record<string, string> = {
  completed: "Завершён",
  in_progress: "В пути",
  pending: "Запланирован",
  delayed: "Задерживается",
};

const documentReviewLabel: Record<string, string> = {
  verified: "Проверено системой",
  pending: "Ожидает проверки",
  needs_attention: "Требует внимания",
  missing: "Нет файла",
};

export default function ShipmentDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(false);
  const [notes, setNotes] = useState("");
  const [ports, setPorts] = useState<InfrastructurePort[]>([]);
  const [portsUnavailable, setPortsUnavailable] = useState(false);
  const [railStatuses, setRailStatuses] = useState<InfrastructureRailStatus[]>([]);
  const { shared, goBack } = useShipmentDetailNavigation(id);
  const backHref = readReturnHref();

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
    Promise.allSettled([apiGet<InfrastructurePort[]>("/ports"), loadLiveInfrastructure()])
      .then(([demoResult, liveResult]) => {
        const demoPorts = demoResult.status === "fulfilled" ? demoResult.value : [];
        const live = liveResult.status === "fulfilled" ? liveResult.value : null;
        const liveByName = new Map(live?.ports.map((port) => [port.name, port]) ?? []);
        setPorts(demoPorts.map((port) => {
          const status = liveByName.get(port.name);
          return status ? { ...port, ...status, sourceKind: "live" } : port;
        }));
        setRailStatuses(live?.rail ?? []);
        setPortsUnavailable(demoResult.status === "rejected" && !live);
      });
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
  const stages = data.route.stages.map((stage) => ({
    location: String(stage.location),
    nextLocation: String(stage.nextLocation),
    transportType: String(stage.transportType),
  }));
  const statusText = statusLabel[String(s.status)] ?? String(s.status);
  const riskText = riskLabel[String(p.riskLevel)] ?? String(p.riskLevel);
  const reasons = (p.reasons as string[]) ?? [];

  return (
    <div className={styles.detailPage}>
      <a className={styles.backLink} href={backHref} onClick={(event) => goBack(event, backHref)}>
        ← {backHref === "/" ? "На главную" : "К списку грузов"}
      </a>

      <header className={styles.detailHeading}>
        <div>
          <div className={styles.detailId}>{id}</div>
          <h1 tabIndex={-1} id="screen-title">
            {String(s.origin)} → {String(s.destination)}
          </h1>
          <p className="muted">{String(s.name)}</p>
        </div>
        <span className={styles.status} data-status={String(s.status)}>
          {statusText}
        </span>
      </header>

      <div className={styles.detailGrid}>
        <section className={styles.mapShell} data-shared-shell={shared || undefined} aria-label="Маршрут отправления">
          <RoutePreview
            origin={String(s.origin)}
            destination={String(s.destination)}
            stages={stages}
            detail
            sharedMap={shared}
          />
        </section>

        <aside className={`${styles.detailAside} reveal`}>
          <h2>Сроки и риск</h2>
          <p>
            <small>Прогноз прибытия (МСК)</small>
            <br />
            <span className={styles.forecastValue}>{formatArrivalRu(String(s.predictedArrival))}</span>
          </p>
          <p>
            <small>Плановая доставка</small>
            <br />
            <b>{formatArrivalRu(String(s.plannedArrival))}</b>
          </p>
          <p>
            <small>Отклонение (ч)</small>
            <br />
            <b>{String(p.estimatedDelay)}</b>
          </p>
          <p>
            <small>Риск</small>
            <br />
            <b>
              {riskText} · {String(p.probability)}%
            </b>
          </p>
          {reasons.length > 0 && (
            <div className={styles.problemBox} role="note">
              <strong>Возможные причины</strong>
              <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                {reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              {"recommendation" in p && p.recommendation ? (
                <p style={{ marginTop: 8 }}>{String(p.recommendation)}</p>
              ) : null}
            </div>
          )}
        </aside>
      </div>

      <div className={`${styles.detailLower} reveal`}>
        <InfrastructureStatus
          stages={data.route.stages.map((stage) => ({
            location: String(stage.location),
            nextLocation: String(stage.nextLocation),
            transportType: String(stage.transportType),
            status: String(stage.status),
            delayHours: Number(stage.delayHours ?? 0),
          }))}
          ports={ports}
          portsUnavailable={portsUnavailable}
          railStatuses={railStatuses}
        />
        <section className={styles.detailSection}>
          <h2>Общая информация</h2>
          <ul>
            <li>Отправитель: {String(s.sender)}</li>
            <li>Получатель: {String(s.receiver)}</li>
            <li>Вес: {String(s.weight)} т</li>
            <li>Контейнеров: {String(s.containerCount)}</li>
            <li>Текущее место: {String(s.currentLocation)}</li>
          </ul>
        </section>

        <section className={styles.detailSection}>
          <h2>Этапы маршрута ({data.route.name})</h2>
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

        <section className={styles.detailSection}>
          <h2>История перемещения</h2>
          <ol className={styles.timeline}>
            {data.history.map((ev, i) => (
              <li key={i} className={styles.timelineItem} data-status={String(ev.status)}>
                <span className={styles.timelineDot} aria-hidden="true" />
                <div className={styles.timelineContent}>
                  <div className={styles.timelineHead}>
                    <strong>{String(ev.location)}</strong>
                    <span className={styles.eventStatus} data-status={String(ev.status)}>
                      {eventStatusLabel[String(ev.status)] ?? String(ev.status)}
                    </span>
                  </div>
                  <p>{String(ev.description)}</p>
                  <div className={styles.timelineMeta}>
                    <time>{formatArrivalRu(String(ev.time))} МСК</time>
                    <span>{transportLabel[String(ev.transport)] ?? String(ev.transport)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.detailSection}>
          <div className={styles.sectionTitleRow}>
            <h2>Документы</h2>
            <span>{data.documents.length} в комплекте</span>
          </div>
          <ul className={styles.documentList}>
            {data.documents.map((d) => (
              <li key={String(d.id)} className={styles.documentRow}>
                <span className={styles.documentIcon} aria-hidden="true">▤</span>
                <div>
                  <strong>{String(d.name)}</strong>
                  {Boolean(d.comment) && <small>{String(d.comment)}</small>}
                </div>
                <span className={styles.documentStatus} data-status={String(d.status)}>
                  {documentReviewLabel[String(d.status)] ?? docStatusLabel[String(d.status)] ?? String(d.status)}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.detailSection}>
          <h2>Экологические показатели</h2>
          <div className={styles.carbonSummary}>
            <div><small>Углеродный след · деморасчёт</small><strong>{data.carbon.total} <span>кг CO₂e</span></strong></div>
            <Link className="button-link" href={`/ecology?shipment=${id}`}>
              Подробнее в экологии →
            </Link>
          </div>
          <ul className={styles.carbonList}>
            {data.carbon.stages.map((row, i) => (
              <li key={i}>
                <span>{String(row.from)} → {String(row.to)}</span><b>{String(row.co2Emission)} кг</b>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.detailSection}>
          <h2>Редактирование</h2>
          {!edit ? (
            <button type="button" className={styles.editButton} onClick={() => setEdit(true)}>
              Редактировать груз
            </button>
          ) : (
            <div className={styles.editForm}>
              <label>
                Дополнительная информация
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} />
              </label>
              <div className={styles.editActions}>
                <button type="button" className={styles.primaryButton} onClick={saveNotes}>Сохранить</button>
                <button type="button" onClick={() => setEdit(false)}>Отмена</button>
              </div>
            </div>
          )}
          {String(s.notes) && !edit && <p className={styles.notes}>{String(s.notes)}</p>}
        </section>
      </div>
    </div>
  );
}
