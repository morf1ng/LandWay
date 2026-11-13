"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { riskLabel } from "@/lib/labels";
import { formatDateTime, formatHours } from "@/lib/format";

type HistoryFeatures = {
  bufferHoursAtForecast?: number | null;
  windSpeedMs?: number;
  portWorkload?: number;
  direction?: string;
};

type ActionPlan = {
  problem: string;
  solutions: string[];
};

type AnalyticsRow = {
  id: string;
  route: string;
  probability: number;
  riskLevel: string;
  reasons: string[];
  estimatedDelay: number;
  predictedArrival: string;
  recommendation: string;
  calculatedAt: string;
  actionPlans?: ActionPlan[];
  historyMode?: string;
  historySource?: string;
  historyMatchCount?: number;
  historyCorridor?: string | null;
  historyNote?: string;
  historyFeatures?: HistoryFeatures;
  historyFactors?: string[];
  historyPoolSize?: number;
  historyMissRate?: number;
  historyMissedCount?: number;
  historyMedianDelayHours?: number;
};

type Analytics = {
  disclaimer: string;
  calculatedAt: string | null;
  corridorHistory?: { source: string; corridor: string; observationCount: number };
  historyBacktest?: {
    dataSource: string;
    corridor: string;
    trainTrips: number;
    evaluatedTrips: number;
    modelMaeHours: number | null;
    heuristicMaeHours: number | null;
    historySamplesUsed: number;
    note: string;
  };
  rows: AnalyticsRow[];
};

type AIAnalysis = {
  shipmentId: string;
  model: string;
  analysis: string;
  actionPlans?: ActionPlan[];
  generatedAt: string;
  source: string;
};

function historyModeLabel(mode?: string) {
  if (mode === "history_blend") return "История + эвристика";
  if (mode === "heuristic_fallback") return "Только эвристика (мало похожих рейсов)";
  if (mode === "not_applicable") return "История не применима к маршруту";
  return "—";
}

function fmtHours(value?: number | null) {
  return value == null ? "—" : formatHours(value);
}

function formatDate(value: string) {
  return formatDateTime(value);
}

function AnalyticsInner() {
  const search = useSearchParams();
  const focus = search.get("shipment");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState<string | null>(focus);
  const [aiResult, setAiResult] = useState<AIAnalysis | null>(null);
  const [aiError, setAiError] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    setAiResult(null);
    setAiError("");
  }, [detailId]);

  function load() {
    apiGet<Analytics>("/analytics")
      .then((d) => {
        setData(d);
        if (focus) setDetailId(focus);
      })
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    load();
  }, [focus]);

  async function recalculate() {
    setError("");
    try {
      const d = await apiPost<Analytics>("/analytics/recalculate", {});
      setData(d);
      setAiResult(null);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function reloadHistory() {
    setHistoryLoading(true);
    setError("");
    try {
      const d = await apiPost<Analytics>("/analytics/history/reload", {});
      setData(d);
      setAiResult(null);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setHistoryLoading(false);
    }
  }

  async function analyzeWithAI(id: string) {
    setAiError("");
    setAiResult(null);
    setAiLoading(true);
    try {
      const result = await apiPost<AIAnalysis>(`/analytics/ai/${encodeURIComponent(id)}`, {});
      setAiResult(result);
    } catch (e) {
      setAiError(String((e as Error).message));
    } finally {
      setAiLoading(false);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Загрузка…</p>;

  const detail = data.rows.find((r) => r.id === detailId);
  const backtest = data.historyBacktest;
  const corridor = data.corridorHistory;

  return (
    <div className="appPage">
      <h1>ИИ-аналитика и прогнозирование</h1>
      <p className="pageLead">{data.disclaimer}</p>
      <div className="actionRow">
        <button type="button" className="primaryAction" onClick={recalculate}>
          Пересчитать прогноз
        </button>
        <button type="button" onClick={reloadHistory} disabled={historyLoading}>
          {historyLoading ? "Загрузка истории…" : "Загрузить демо-историю коридора"}
        </button>
        {data.calculatedAt && <span className="muted">Последний расчёт: {formatDate(data.calculatedAt)}</span>}
      </div>

      {corridor && (
        <section className="analyticsCorridor" aria-labelledby="corridor-history-title">
          <h2 id="corridor-history-title">История коридора ж/д → паром</h2>
          <p>
            <strong>{corridor.corridor}</strong> · источник: <span className="muted">{corridor.source} (воспроизводимый набор, seed=42)</span> ·
            {" "}
            {corridor.observationCount} рейсов
          </p>
          {backtest && (
            <div className="analyticsBacktest">
              <span className="demoTag">Демо-проверка</span>
              <p>
                Средняя ошибка прогноза задержки (MAE) на {backtest.evaluatedTrips} более поздних рейсах:{" "}
                <strong>{fmtHours(backtest.modelMaeHours)}</strong> — текущая модель, {fmtHours(backtest.heuristicMaeHours)} — только
                эвристика. История сработала в {backtest.historySamplesUsed} из {backtest.evaluatedTrips} случаев, в остальных
                модель честно откатилась к эвристике. Обучение на {backtest.trainTrips} ранних рейсах.
              </p>
              <small className="muted">{backtest.note}</small>
            </div>
          )}
        </section>
      )}

      <section>
        <h2>Все грузы</h2>
        <table className="analyticsTable">
          <thead>
            <tr>
              <th>ID</th>
              <th>Маршрут</th>
              <th>Риск стыковки</th>
              <th>История</th>
              <th>Причины</th>
              <th>Задержка доставки</th>
              <th>Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.id} data-selected={row.id === detailId ? true : undefined}>
                <td data-label="Груз">
                  <button type="button" aria-pressed={row.id === detailId} onClick={() => setDetailId(row.id)}>
                    {row.id}
                  </button>
                </td>
                <td data-label="Маршрут">{row.route}</td>
                <td data-label="Вероятность">
                  {row.probability}% ({riskLabel[row.riskLevel] ?? row.riskLevel})
                </td>
                <td data-label="История">
                  {row.historyMode === "history_blend"
                    ? `похожих ${row.historyMatchCount ?? 0}`
                    : historyModeLabel(row.historyMode)}
                </td>
                <td data-label="Причины">{row.reasons.join("; ")}</td>
                <td data-label="Задержка">{row.estimatedDelay} ч</td>
                <td data-label="Рекомендация">{row.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {detail && (
        <section className="analyticsDetail" aria-labelledby="analytics-detail-title">
          <div className="analyticsDetailHead">
            <div>
              <span className="analyticsDetailEyebrow">ПРОГНОЗ ПО ГРУЗУ · {detail.id}</span>
              <h2 id="analytics-detail-title">{detail.route}</h2>
            </div>
            <span className="analyticsRisk" data-risk={detail.riskLevel}>
              Риск {riskLabel[detail.riskLevel] ?? detail.riskLevel}
            </span>
          </div>

          <dl className="analyticsMetrics">
            <div>
              <dt>Риск сорвать стыковку</dt>
              <dd>
                {detail.probability}
                <span>%</span>
              </dd>
            </div>
            <div>
              <dt>Прогноз доставки (ETA)</dt>
              <dd>{formatDate(detail.predictedArrival)}</dd>
            </div>
            <div>
              <dt>Задержка к контрактному сроку</dt>
              <dd>
                {detail.estimatedDelay}
                <span> ч</span>
              </dd>
            </div>
            <div>
              <dt>Режим прогноза</dt>
              <dd>{historyModeLabel(detail.historyMode)}</dd>
            </div>
          </dl>

          {(detail.historyMode === "history_blend" || detail.historyMode === "heuristic_fallback") && detail.historyCorridor && (
            <CorridorHistoryBlock detail={detail} />
          )}

          <div className="analyticsDetailBody">
            <div className="analyticsCauses">
              <h3>Факторы риска</h3>
              <ul>
                {detail.reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
            <div className="analyticsRecommendation">
              <span className="analyticsRecommendationLabel">РЕКОМЕНДАЦИЯ</span>
              <p>{detail.recommendation}</p>
              <Link className="button-link primaryAction" href={`/shipments/${detail.id}`}>
                Открыть карточку груза <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
          <ActionPlansBlock
            plans={
              aiResult?.shipmentId === detail.id && aiResult.actionPlans?.length
                ? aiResult.actionPlans
                : detail.actionPlans ?? []
            }
            summary={aiResult?.shipmentId === detail.id ? aiResult.analysis : undefined}
            aiMeta={
              aiResult?.shipmentId === detail.id
                ? `Ответ модели · ${formatDate(aiResult.generatedAt)} · ${aiResult.source === "demo_forecast_ai" ? "формулировки уточнены ИИ" : "готовые шаги с сервера"}`
                : "Готовые шаги по факторам риска · без вызова ИИ"
            }
            onAnalyze={() => analyzeWithAI(detail.id)}
            aiLoading={aiLoading}
            aiRequested={aiResult?.shipmentId === detail.id}
            aiError={aiError}
          />
          <p className="analyticsCalculated">
            Расчёт обновлён {formatDate(detail.calculatedAt)}
            {detail.historySource === "synthetic" ? " · синтетическая история коридора" : ""}
          </p>
        </section>
      )}
    </div>
  );
}

function ActionPlansBlock({
  plans,
  summary,
  aiMeta,
  onAnalyze,
  aiLoading,
  aiRequested,
  aiError,
}: {
  plans: ActionPlan[];
  summary?: string;
  aiMeta: string;
  onAnalyze: () => void;
  aiLoading: boolean;
  aiRequested: boolean;
  aiError: string;
}) {
  if (!plans.length) return null;
  return (
    <div className="aiAnalysis">
      <div className="aiAnalysisHead">
        <div>
          <h3>Готовые решения для логиста</h3>
          <p>По каждой проблеме — 3 условных шага «если … — …». Цифры прогноза не меняются.</p>
        </div>
        <button type="button" onClick={onAnalyze} disabled={aiLoading}>
          {aiLoading ? "Анализируем…" : aiRequested ? "Обновить формулировки ИИ" : "Уточнить ИИ"}
        </button>
      </div>
      {aiError && (
        <p className="error" role="alert">
          {aiError}
        </p>
      )}
      {summary && <p className="aiAnalysisSummary">{summary}</p>}
      <div className="aiActionPlanList">
        {plans.map((plan) => (
          <article key={plan.problem} className="aiActionPlan">
            <h4>{plan.problem}</h4>
            <ol>
              {plan.solutions.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </article>
        ))}
      </div>
      <small className="muted">{aiMeta} · данные демонстрационные</small>
    </div>
  );
}

function CorridorHistoryBlock({ detail }: { detail: AnalyticsRow }) {
  const f = detail.historyFeatures;
  const factors = detail.historyFactors ?? [];
  return (
    <div className="analyticsHistory">
      <h3>Прогноз по похожим рейсам</h3>
      <p className="muted">
        {detail.historyNote}
        {detail.historySource === "synthetic" ? " · данные synthetic, не оперативная статистика перевозчика" : ""}
      </p>
      <ul>
        <li>
          Похожих рейсов: <strong>{detail.historyMatchCount ?? 0}</strong>
          {detail.historyPoolSize ? ` из ${detail.historyPoolSize}` : ""}
          {detail.historyMode === "heuristic_fallback" ? " — меньше 3, расчёт только по эвристике" : ""}
        </li>
        {f && (
          <li>
            Признаки на момент прогноза: запас стыковки {fmtHours(f.bufferHoursAtForecast)},
            ветер {f.windSpeedMs ?? "—"} м/с, загрузка порта {f.portWorkload != null ? `${Math.round(f.portWorkload)}%` : "—"}
          </li>
        )}
        {factors.length > 0 && <li>Похожими считаются рейсы: {factors.join("; ")}</li>}
        {detail.historyMode === "history_blend" && (
          <li>
            Среди похожих паром пропущен в {detail.historyMissedCount ?? "—"} из {detail.historyMatchCount ?? "—"} рейсов
            {detail.historyMissRate != null ? ` (${Math.round(detail.historyMissRate * 100)}%)` : ""}, медианная задержка доставки{" "}
            {fmtHours(detail.historyMedianDelayHours)}
          </li>
        )}
      </ul>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <AnalyticsInner />
    </Suspense>
  );
}
