"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel } from "@/lib/labels";
import styles from "./notifications.module.css";
import { formatDateTime } from "@/lib/format";

type Row = {
  id: string;
  name: string;
  route: string;
  probability: number;
  riskLevel: string;
  reasons: string[];
  estimatedDelay: number;
  predictedArrival: string;
  recommendation: string;
  calculatedAt: string;
};
type Analysis = { shipmentId: string; analysis: string; generatedAt: string; model: string };

function date(value: string) {
  return formatDateTime(value);
}

export default function NotificationsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, Analysis>>({});
  const [failed, setFailed] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await apiGet<{ rows: Row[] }>("/analytics");
        if (cancelled) return;
        const riskRows = result.rows.filter((row) => row.riskLevel === "high" || row.riskLevel === "medium");
        setRows(riskRows);
        setSelected(riskRows[0]?.id ?? null);
        setLoading(false);
        // One AI explanation per at-risk shipment. The calculated forecast remains the source of numeric facts.
        for (const row of riskRows) {
          if (cancelled) break;
          try {
            const analysis = await apiPost<Analysis>(`/analytics/ai/${encodeURIComponent(row.id)}`, {});
            if (!cancelled) setAnalyses((previous) => ({ ...previous, [row.id]: analysis }));
          } catch (cause) {
            if (!cancelled) setFailed((previous) => ({ ...previous, [row.id]: String((cause as Error).message) }));
          }
        }
      } catch (cause) {
        if (!cancelled) { setError(String((cause as Error).message)); setLoading(false); }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const current = useMemo(() => rows.find((row) => row.id === selected) ?? null, [rows, selected]);

  if (loading) return <div className={styles.page}><h1>Уведомления</h1><p>Загрузка уведомлений…</p></div>;
  if (error) return <div className={styles.page}><h1>Уведомления</h1><p className="error">{error}</p></div>;

  return (
    <div className={styles.page}>
      <div className={styles.heading}>
        <div><h1>Уведомления</h1><p>По одному уведомлению на груз, который требует внимания. Данные и прогноз демонстрационные.</p></div>
        <span className={styles.count}>{rows.length} {rows.length === 1 ? "груз" : rows.length < 5 ? "груза" : "грузов"}</span>
      </div>
      {rows.length === 0 ? <div className={styles.empty}>Грузов с повышенным риском сейчас нет.</div> : (
        <div className={styles.layout}>
          <div className={styles.list} aria-label="Уведомления по грузам">
            {rows.map((row) => (
              <button type="button" key={row.id} className={styles.item} data-severity={row.riskLevel} aria-pressed={row.id === selected} onClick={() => setSelected(row.id)}>
                <span className={styles.itemTop}><span>{riskLabel[row.riskLevel] ?? "Риск"}</span><strong>{row.id}</strong></span>
                <strong className={styles.route}>{row.route}</strong>
                <span className={styles.itemText}>{analyses[row.id]?.analysis ?? (failed[row.id] ? row.reasons[0] : "ИИ готовит разбор факторов риска…")}</span>
                <span className={styles.itemFoot}>Риск {row.probability}% · {row.estimatedDelay ? `задержка ${row.estimatedDelay} ч` : "без задержки"} · {analyses[row.id] ? "анализ ИИ" : "прогноз системы"}</span>
              </button>
            ))}
          </div>
          {current && <section className={styles.detail} aria-label={`Уведомление по грузу ${current.id}`}>
            <div className={styles.detailTop}><span className={styles.badge} data-severity={current.riskLevel}>{riskLabel[current.riskLevel] ?? "Риск"}</span><span>{current.id}</span></div>
            <h2>{current.route}</h2>
            <p className={styles.cargo}>{current.name}</p>
            <div className={styles.facts}>
              <div><span>Вероятность задержки</span><strong>{current.probability}%</strong></div>
              <div><span>Ожидаемая задержка</span><strong>{current.estimatedDelay} ч</strong></div>
              <div><span>Прогноз доставки</span><strong>{date(current.predictedArrival)}</strong></div>
            </div>
            <h3>Факторы риска</h3>
            <ul className={styles.reasons}>{current.reasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul>
            <div className={styles.aiBlock}>
              <span className={styles.label}>Разбор Nemotron 3.5 Lightning</span>
              <p>{analyses[current.id]?.analysis ?? (failed[current.id] ? "ИИ сейчас недоступен. Расчётный прогноз и факторы риска показаны выше." : "ИИ готовит разбор по данным выбранного груза…")}</p>
              {analyses[current.id] && <small>Сформировано {date(analyses[current.id].generatedAt)} · текст ИИ, не подтверждение перевозчика</small>}
              {failed[current.id] && <small>{failed[current.id]}</small>}
            </div>
            <div className={styles.recommendation}><span className={styles.label}>Рекомендация расчётной модели</span><p>{current.recommendation}</p></div>
            <div className={styles.actions}><Link href={`/shipments/${encodeURIComponent(current.id)}`}>Открыть груз</Link><Link href={`/analytics?shipment=${encodeURIComponent(current.id)}`}>Подробный прогноз</Link></div>
          </section>}
        </div>
      )}
    </div>
  );
}
