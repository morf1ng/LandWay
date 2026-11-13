"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { RoutePreview } from "@/components/shipments/RoutePreview";
import { InfrastructureStatus } from "@/components/InfrastructureStatus";
import styles from "@/components/shipments/shipmentCards.module.css";
import { useShipmentDetailNavigation } from "@/hooks/useShipmentCardNavigation";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { docStatusLabel, riskLabel, statusLabel, transportLabel } from "@/lib/labels";
import { formatArrivalRu } from "@/lib/shipments/format";
import { formatDateTime, formatHours, formatKgCo2, parseServerDate } from "@/lib/format";
import { loadLiveInfrastructure, type InfrastructurePort, type InfrastructureRailStatus } from "@/lib/infrastructure";

type Stage = {
  id: string;
  location: string;
  nextLocation: string;
  transportType: string;
  status: string;
  plannedStart?: string | null;
  plannedArrival?: string | null;
  actualArrival?: string | null;
  delayHours?: number | null;
  shipDeparture?: string | null;
};

type StageSource = { sourceName: string; sourceKind: string; observedAt: string; eventId: string };

const stageStatusLabel: Record<string, string> = {
  completed: "пройден",
  in_progress: "в пути",
  delayed: "в пути с опозданием",
  pending: "впереди",
};

function sourceText(source: StageSource) {
  const simulated = source.sourceKind === "simulation" && !source.sourceName.toLowerCase().includes("симуляц");
  return simulated ? `${source.sourceName} (симуляция)` : source.sourceName;
}

function stageArrival(stage: Stage): Date | null {
  if (stage.actualArrival) return parseServerDate(stage.actualArrival);
  const planned = parseServerDate(stage.plannedArrival);
  if (!planned) return null;
  return new Date(planned.getTime() + Number(stage.delayHours ?? 0) * 3600_000);
}

function connectionState(stages: Stage[]) {
  const index = stages.findIndex((stage) => stage.status !== "completed");
  if (index < 0) return null;
  const active = stages[index];
  const next = stages[index + 1];
  if (!next || next.transportType !== "sea" || active.transportType === "sea" || !next.shipDeparture) return null;
  const arrival = stageArrival(active);
  const departure = parseServerDate(next.shipDeparture);
  if (!arrival || !departure) return null;
  const bufferHours = (departure.getTime() - arrival.getTime()) / 3600_000;
  return { port: next.location, arrival, departure, bufferHours };
}

type Detail = {
  shipment: Record<string, unknown>;
  route: { stages: Stage[]; name: string };
  stageSources?: Record<string, StageSource>;
  prediction: Record<string, unknown>;
  documents: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  carbon: { total: number; stages: Array<Record<string, unknown>> };
  preclearance?: {
    preclearanceStatus?: string | null;
    preclearanceAt?: string | null;
    preclearanceStale?: boolean;
    preclearanceStaleMessage?: string | null;
  };
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
  const [actionError, setActionError] = useState("");
  const [edit, setEdit] = useState(false);
  const [notes, setNotes] = useState("");
  const [ports, setPorts] = useState<InfrastructurePort[]>([]);
  const [portsUnavailable, setPortsUnavailable] = useState(false);
  const [railStatuses, setRailStatuses] = useState<InfrastructureRailStatus[]>([]);
  const { preview, backHref, goBack } = useShipmentDetailNavigation(id);
  const [infraExternal, setInfraExternal] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simMessage, setSimMessage] = useState("");

  function load() {
    setError("");
    return apiGet<Detail>(`/shipments/${encodeURIComponent(id)}`)
      .then((d) => {
        setData(d);
        setNotes(String(d.shipment.notes ?? ""));
        return d;
      })
      .catch((e) => {
        setError(String(e.message || e));
        return null;
      });
  }

  function refreshInfrastructure() {
    return Promise.allSettled([apiGet<InfrastructurePort[]>("/ports"), loadLiveInfrastructure()]).then(
      ([demoResult, liveResult]) => {
        const demoPorts = demoResult.status === "fulfilled" ? demoResult.value : [];
        const live = liveResult.status === "fulfilled" ? liveResult.value : null;
        const liveByName = new Map(live?.ports.map((port) => [port.name, port]) ?? []);
        setPorts(
          demoPorts.map((port) => {
            const status = liveByName.get(port.name);
            return status ? { ...port, ...status, sourceKind: status.sourceKind ?? "live" } : port;
          })
        );
        setRailStatuses(live?.rail ?? []);
        setInfraExternal(Boolean(live?.externalConnected));
        setPortsUnavailable(demoResult.status === "rejected" && !live);
      }
    );
  }

  useEffect(() => {
    load();
    void refreshInfrastructure();
  }, [id]);

  async function simulatePortClose(withEnd: boolean) {
    setSimulating(true);
    setSimMessage("");
    setActionError("");
    try {
      const body = withEnd ? { restrictionEndsAt: "2026-11-13T14:00:00" } : undefined;
      const result = await apiPost<{ telemetry: { status: string; message?: string } }>(
        `/shipments/${encodeURIComponent(id)}/simulate/port-departure-closed`,
        body
      );
      await load();
      await refreshInfrastructure();
      setSimMessage(
        result.telemetry.status === "duplicate"
          ? "Событие уже было учтено."
          : "Порт (симуляция): выход для судов закрыт, прогноз пересчитан."
      );
    } catch (e) {
      setActionError(String((e as Error).message));
    } finally {
      setSimulating(false);
    }
  }

  async function simulatePortOpen() {
    setSimulating(true);
    setSimMessage("");
    setActionError("");
    try {
      const result = await apiPost<{ telemetry: { status: string } }>(
        `/shipments/${encodeURIComponent(id)}/simulate/port-departure-open`
      );
      await load();
      await refreshInfrastructure();
      setSimMessage(
        result.telemetry.status === "duplicate"
          ? "Событие уже было учтено."
          : "Порт (симуляция): выход для судов открыт."
      );
    } catch (e) {
      setActionError(String((e as Error).message));
    } finally {
      setSimulating(false);
    }
  }

  async function simulateRailMessage() {
    setSimulating(true);
    setSimMessage("");
    setActionError("");
    const etaBefore = data ? String(data.shipment.predictedArrival) : "";
    try {
      const result = await apiPost<{ telemetry: { status: string; eventId: string; message?: string } }>(
        `/shipments/${encodeURIComponent(id)}/simulate/rail-delay`
      );
      const status = result.telemetry.status;
      const fresh = await load();
      await refreshInfrastructure();
      const etaAfter = fresh ? String(fresh.shipment.predictedArrival) : "";
      if (status === "duplicate") {
        setSimMessage("Это сообщение уже было учтено — повтор не изменил прогноз.");
      } else if (status === "stale") {
        setSimMessage("Сообщение устарело: по этапу уже есть более свежие данные, прогноз не изменён.");
      } else {
        setSimMessage(
          `Сообщение РЖД (симуляция) принято и сохранено. Прогноз прибытия: ${formatDateTime(etaBefore)} → ${formatDateTime(etaAfter, true)}.`
        );
      }
    } catch (e) {
      setActionError(String((e as Error).message));
    } finally {
      setSimulating(false);
    }
  }

  async function saveNotes() {
    setActionError("");
    try {
      await apiPatch(`/shipments/${encodeURIComponent(id)}`, { notes });
      setEdit(false);
      await load();
    } catch (e) {
      setActionError(String((e as Error).message));
    }
  }

  const s = data?.shipment ?? {};
  const p = data?.prediction ?? {};
  const routeStages = data?.route.stages ?? [];
  const origin = data ? String(s.origin) : preview?.origin;
  const destination = data ? String(s.destination) : preview?.destination;
  const status = data ? String(s.status) : preview?.status;
  const statusText = status ? statusLabel[status] ?? status : "";
  const riskText = riskLabel[String(p.riskLevel)] ?? String(p.riskLevel);
  const reasons = (p.reasons as string[]) ?? [];
  const activeStage = routeStages.find((stage) => stage.status !== "completed");
  const activeSource = activeStage ? data?.stageSources?.[activeStage.id] : undefined;
  const connection = connectionState(routeStages);
  const hasRailSea =
    routeStages.some((stage) => stage.transportType === "rail") &&
    routeStages.some((stage) => stage.transportType === "sea");

  return (
    <div className={styles.detailPage}>
      <a className={styles.backLink} href={backHref} onClick={goBack}>
        <span>{backHref === "/" ? "Главная панель" : "Грузы"}</span>
        <span className={styles.backLinkIcon}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path
              d={
                backHref === "/"
                  ? "M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-7H10v7H5a1 1 0 0 1-1-1z"
                  : "M5 9.5 12 5.5l7 4V18l-7 4-7-4V9.5z M12 5.5V22 M8.5 11.5v9.5 M15.5 11.5v9.5"
              }
            />
          </svg>
        </span>
      </a>

      <header className={styles.detailHeading}>
        <div>
          <div className={styles.detailId}>{id}</div>
          <h1 tabIndex={-1} id="screen-title">
            {origin && destination ? `${origin} → ${destination}` : `Груз ${id}`}
          </h1>
          {(data || preview) && <p className="muted">{data ? String(s.name) : preview?.name}</p>}
        </div>
        {status && (
          <span className={styles.status} data-status={status}>
            {statusText}
          </span>
        )}
      </header>

      <div className={styles.detailGrid}>
        {origin && destination && (
          <section id={`detail-map-${id}`} className={styles.mapShell} aria-label="Маршрут отправления">
            <div data-shipment-map className={styles.detailMap}>
              <RoutePreview origin={origin} destination={destination} stages={data?.route.stages} detail />
            </div>
          </section>
        )}

        <aside className={styles.detailAside} data-shipment-reveal aria-busy={!data && !error}>
          {!data ? (
            error ? (
              <>
                <p className="error" role="alert">Не удалось загрузить груз {id}: {error}</p>
                <button type="button" onClick={() => void load()}>Повторить</button>
              </>
            ) : <p className="muted" role="status">Загружаем прогноз и этапы…</p>
          ) : <>
            <h2>Сроки и риск</h2>
            {actionError ? (
              <p className="error" role="alert">
                {actionError}
              </p>
            ) : null}
            <p>
              <small>Прогноз прибытия (МСК)</small>
              <br />
              <span className={styles.forecastValue}>
                {Boolean((p as { etaUnknown?: boolean }).etaUnknown) || !s.predictedArrival
                  ? "не определён (ограничение порта)"
                  : formatArrivalRu(String(s.predictedArrival))}
              </span>
            </p>
            <p>
              <small>Срок по контракту · задержка к нему</small>
              <br />
              <b>
                {formatArrivalRu(String(s.plannedArrival))} ·{" "}
                {(p as { etaUnknown?: boolean }).etaUnknown || p.estimatedDelay == null
                  ? "задержка не определена"
                  : formatHours(Number(p.estimatedDelay))}
              </b>
            </p>
            <p>
              <small>Риск сорвать стыковку</small>
              <br />
              <b>
                {riskText} · {String(p.probability)}%
              </b>
            </p>
            {activeStage ? (
              <div className={styles.stageNow}>
                <small>Текущий этап</small>
                <b>
                  {activeStage.location} → {activeStage.nextLocation} · {transportLabel[activeStage.transportType] ?? activeStage.transportType}
                </b>
                <span>
                  {stageStatusLabel[activeStage.status] ?? activeStage.status}
                  {Number(activeStage.delayHours ?? 0) > 0 ? `, опоздание ${formatHours(Number(activeStage.delayHours))}` : ""}
                  {stageArrival(activeStage) ? `, прибытие в ${activeStage.nextLocation} ≈ ${formatDateTime(stageArrival(activeStage)!.toISOString(), true)}` : ""}
                </span>
                <span className="muted">
                  {activeSource
                    ? `Источник: ${sourceText(activeSource)} · наблюдение ${formatDateTime(activeSource.observedAt, true)}`
                    : "Источник: план перевозки (оперативных сообщений по этапу не было)"}
                </span>
              </div>
            ) : null}
            {connection ? (
              <div className={styles.connectionBox} data-missed={connection.bufferHours < 0 || undefined}>
                <small>Стыковка в порту {connection.port}</small>
                <b>
                  {connection.bufferHours >= 0
                    ? `Запас ${formatHours(connection.bufferHours)} до отхода парома`
                    : `Поезд опоздает к парому на ${formatHours(-connection.bufferHours)}`}
                </b>
                <span className="muted">
                  Отход парома {formatDateTime(connection.departure.toISOString(), true)}
                </span>
              </div>
            ) : null}
            {p.calculatedAt ? (
              <p>
                <small>Прогноз пересчитан</small>
                <br />
                <b>{formatDateTime(String(p.calculatedAt), true)}</b>
              </p>
            ) : null}
            {reasons.length > 0 && (
              <div className={styles.problemBox} role="note">
                <strong>Почему такой прогноз</strong>
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            {s.status !== "delivered" ? (
              <div className={styles.nextAction}>
                <small>Следующее действие</small>
                <p>{String(p.recommendation ?? "Следить за этапом")}</p>
                <Link className={styles.primaryButton} href={`/routes?shipment=${encodeURIComponent(id)}`}>
                  Сравнить варианты маршрута
                </Link>
              </div>
            ) : null}
            {hasRailSea && s.status !== "delivered" ? (
              <div className={styles.demoSimBox}>
                <p className="muted" style={{ margin: 0 }}>
                  <span className="demoTag">Демо</span> Поток РЖД не подключён. Кнопка отправляет учебное сообщение
                  «поезд опаздывает на 52 ч» через тот же API событий, что и внешний источник.
                </p>
                <button type="button" className={styles.simulateButton} disabled={simulating} onClick={() => void simulateRailMessage()}>
                  {simulating ? "Отправка…" : "Симулировать сообщение от ж/д"}
                </button>
                <p className="muted" style={{ margin: "10px 0 0" }}>
                  <span className="demoTag">Демо</span> Закрытие/открытие выхода судов — через тот же API событий с меткой
                  «симуляция».
                </p>
                <div className={styles.simButtons}>
                  <button
                    type="button"
                    className={styles.simulateButton}
                    disabled={simulating}
                    onClick={() => void simulatePortClose(true)}
                  >
                    Закрыть выход (до 13.11 14:00)
                  </button>
                  <button type="button" className={styles.simulateButton} disabled={simulating} onClick={() => void simulatePortClose(false)}>
                    Закрыть без даты открытия
                  </button>
                  <button type="button" className={styles.simulateButton} disabled={simulating} onClick={() => void simulatePortOpen()}>
                    Открыть выход
                  </button>
                </div>
                {simMessage ? <p className={styles.simToast} role="status">{simMessage}</p> : null}
              </div>
            ) : null}
          </>}
        </aside>
      </div>

      {data && <div className={styles.detailLower} data-shipment-reveal>
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
          externalConnected={infraExternal}
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
          <ol className={styles.stageList}>
            {routeStages.map((stage) => {
              const source = data.stageSources?.[stage.id];
              const arrival = stageArrival(stage);
              return (
                <li key={stage.id} data-status={stage.status}>
                  <b>
                    {stage.location} → {stage.nextLocation}
                  </b>{" "}
                  ({transportLabel[stage.transportType] ?? stage.transportType}, {stageStatusLabel[stage.status] ?? stage.status})
                  <div className="muted">
                    {stage.transportType === "sea" && stage.shipDeparture
                      ? `Отход ${formatDateTime(stage.shipDeparture)} · `
                      : stage.plannedStart
                        ? `Начало ${formatDateTime(stage.plannedStart)} · `
                        : ""}
                    {stage.actualArrival ? "Прибыл" : "Прибытие"} {arrival ? formatDateTime(arrival.toISOString()) : "—"}
                    {Number(stage.delayHours ?? 0) > 0 ? ` (опоздание ${formatHours(Number(stage.delayHours))})` : ""}
                    {source
                      ? ` · ${sourceText(source)}, ${formatDateTime(source.observedAt)}`
                      : ""}
                  </div>
                </li>
              );
            })}
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
                    <time>{formatDateTime(String(ev.time), true)}</time>
                    <span>{transportLabel[String(ev.transport)] ?? String(ev.transport)}</span>
                    {"sourceName" in ev && ev.sourceName ? (
                      <span>
                        {String(ev.sourceName)}
                        {ev.sourceKind === "simulation" && !String(ev.sourceName).toLowerCase().includes("симуляц") ? " · симуляция" : ""}
                      </span>
                    ) : null}
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
          {data.preclearance?.preclearanceStatus && (
            <p className={styles.preclearanceStatus}>
              Предварительная проверка (демо): <strong>{String(data.preclearance.preclearanceStatus)}</strong>
              {data.preclearance.preclearanceStale ? " — устарело" : ""}
              {data.preclearance.preclearanceAt ? (
                <span> · {formatDateTime(String(data.preclearance.preclearanceAt), true)}</span>
              ) : null}
              {data.preclearance.preclearanceStale && data.preclearance.preclearanceStaleMessage ? (
                <span className={styles.preclearanceStale}> · {data.preclearance.preclearanceStaleMessage}</span>
              ) : null}
            </p>
          )}
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
            <div><small>Углеродный след всего маршрута · деморасчёт</small><strong>{formatKgCo2(data.carbon.total)}</strong></div>
            <Link className="button-link" href={`/ecology?shipment=${id}`}>
              Подробнее в экологии →
            </Link>
          </div>
          <ul className={styles.carbonList}>
            {data.carbon.stages.map((row, i) => (
              <li key={i}>
                <span>{String(row.from)} → {String(row.to)}</span><b>{formatKgCo2(Number(row.co2Emission))}</b>
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
      </div>}
    </div>
  );
}
