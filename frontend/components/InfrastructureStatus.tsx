import {
  infrastructureForRoute,
  type InfrastructurePort,
  type InfrastructureRailStatus,
  type InfrastructureStage,
} from "@/lib/infrastructure";
import styles from "./InfrastructureStatus.module.css";

type Props = {
  stages: InfrastructureStage[];
  ports: InfrastructurePort[];
  portsUnavailable?: boolean;
  railStatuses?: InfrastructureRailStatus[];
};

export function InfrastructureStatus({ stages, ports, portsUnavailable = false, railStatuses = [] }: Props) {
  const relevant = infrastructureForRoute(stages, ports);
  const hasSea = stages.some((stage) => stage.transportType === "sea");
  if (!hasSea && relevant.rail.length === 0) return null;

  return (
    <section className={styles.section} aria-label="Состояние инфраструктуры маршрута">
      <div className={styles.heading}>
        <h2>Инфраструктура маршрута</h2>
        <span className={styles.source}>Данные по маршруту груза</span>
      </div>

      {hasSea && (portsUnavailable || relevant.ports.length === 0) && (
        <div className={styles.row}>
          <span className={styles.icon} aria-hidden="true">▧</span>
          <div className={styles.copy}>
            <strong>Порты маршрута</strong>
            <small>Оперативные данные о загрузке недоступны</small>
          </div>
          <span className={styles.unknown}>Нет данных</span>
        </div>
      )}

      {relevant.ports.map((port) => (
        <div className={styles.row} key={port.name}>
          <span className={styles.icon} aria-hidden="true">▧</span>
          <div className={styles.copy}>
            <strong>Порт {port.name}</strong>
            <small>
              {port.sourceKind === "live"
                ? `${port.sourceName ?? "Оперативный источник"} · ${port.observedAt ? new Date(port.observedAt).toLocaleString("ru-RU") : "время не указано"}`
                : port.delayNote ?? "Расчётный показатель проекта"}
            </small>
          </div>
          <div className={styles.value}>
            <b>{Number.isFinite(port.workload) ? `${Math.round(port.workload!)}%` : "—"}</b>
            <small>{port.sourceKind === "live" ? "Источник" : "Демо"}</small>
          </div>
        </div>
      ))}

      {relevant.rail.map((stage, index) => {
        const actual = railStatuses.find((item) => item.from === stage.location && item.to === stage.nextLocation);
        return <div className={styles.row} key={`${stage.location}-${stage.nextLocation}-${index}`}>
          <span className={styles.icon} aria-hidden="true">╞</span>
          <div className={styles.copy}>
            <strong>Ж/д · {stage.location} → {stage.nextLocation}</strong>
            <small>
              {actual
                ? `${actual.sourceName} · ${new Date(actual.observedAt).toLocaleString("ru-RU")}`
                : Number(stage.delayHours) > 0
                  ? `Отставание поезда: ${Number(stage.delayHours)} ч · данные рейса (демо)`
                  : "Оперативная загрузка участка не подключена"}
            </small>
          </div>
          {actual ? (
            <div className={styles.value}><b>{Number.isFinite(actual.workload) ? `${Math.round(actual.workload!)}%` : "—"}</b><small>Источник</small></div>
          ) : <span className={styles.unknown}>Загрузка: нет данных</span>}
        </div>;
      })}

      <p className={styles.note}>
        Показатели без источника и времени обновления — демоданные. Они не считаются оперативным статусом и не используются как подтверждённые данные перевозчика.
      </p>
    </section>
  );
}
