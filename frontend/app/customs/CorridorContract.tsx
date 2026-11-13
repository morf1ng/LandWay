"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import styles from "./corridorContract.module.css";
import { formatDateTime } from "@/lib/format";

type Block = {
  index: number;
  shipmentId: string;
  hash: string;
  previousHash: string;
  documentDigest: string;
  decision: "ready_for_review" | "needs_correction";
  problems: string[];
  actor: string;
  createdAt: string;
};

type ContractState = {
  shipmentId: string;
  ready: boolean;
  problems: string[];
  documentDigest: string;
  documents: Array<{ id: string; type: string; fileSha256: string | null }>;
  latestBlock: Block | null;
  shipmentBlockCount: number;
  recentBlocks: Block[];
  snapshotMatches: boolean;
  chain: { valid: boolean; height: number; headHash?: string; reason?: string };
  network: string;
  verifierNote?: string;
};

function shortHash(hash: string) {
  return `${hash.slice(0, 12)}…${hash.slice(-10)}`;
}

function formatTime(value: string) {
  return formatDateTime(value, true);
}

function decisionLabel(decision: Block["decision"]) {
  return decision === "ready_for_review" ? "Готов к рассмотрению" : "Требуется исправление";
}

export function CorridorContract({
  shipmentId,
  shipmentIds,
  onShipmentChange,
  version,
  readOnly = false,
}: {
  shipmentId: string;
  shipmentIds: string[];
  onShipmentChange: (id: string) => void;
  version: number;
  readOnly?: boolean;
}) {
  const [state, setState] = useState<ContractState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiGet<ContractState>(`/corridor/contract/${encodeURIComponent(shipmentId)}`)
      .then((value) => {
        if (active) setState(value);
      })
      .catch((cause) => {
        if (active) setError((cause as Error).message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [shipmentId, version]);

  return (
    <section className={styles.section} aria-labelledby="contract-heading">
      <div className={styles.heading}>
        <div>
          <span className={styles.eyebrow}>Локальный реестр · демо</span>
          <h2 id="contract-heading">Записи проверки комплекта</h2>
          <p>
            Каждая подача фиксирует отпечаток документов и решение.{" "}
            {state?.verifierNote ?? "Имитация проверяющей стороны, не таможенный орган."}
          </p>
        </div>
        <span className={styles.network}>1 узел · локальный реестр</span>
      </div>

      {!readOnly && (
        <label className={styles.shipmentPicker}>
          Груз для проверки
          <select value={shipmentId} onChange={(event) => onShipmentChange(event.target.value)}>
            {shipmentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>
      )}

      {loading && <p role="status">Загружаем реестр…</p>}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      {!loading && state?.shipmentId === shipmentId && (
        <>
          <div className={styles.metrics}>
            <div>
              <span>Груз</span>
              <strong>{state.shipmentId}</strong>
            </div>
            <div>
              <span>Текущий комплект</span>
              <strong>{state.ready ? "Без замечаний" : "Есть замечания"}</strong>
            </div>
            <div>
              <span>Целостность реестра</span>
              <strong>{state.chain.valid ? "Подтверждена" : "Нарушена"}</strong>
            </div>
            <div>
              <span>Попыток проверки</span>
              <strong>{state.shipmentBlockCount}</strong>
            </div>
          </div>

          {!state.ready && (
            <div className={styles.notice}>
              <strong>Текущие замечания</strong>
              <ul>
                {state.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}

          {state.latestBlock ? (
            <div className={styles.block}>
              <div className={styles.blockTop}>
                <strong>Последняя запись #{state.latestBlock.index}</strong>
                <span className={state.snapshotMatches ? styles.matched : styles.changed}>
                  {state.snapshotMatches
                    ? "Документы совпадают с записью"
                    : "Решение относится к предыдущей версии комплекта"}
                </span>
              </div>
              <p>
                {decisionLabel(state.latestBlock.decision)} · {formatTime(state.latestBlock.createdAt)} ·{" "}
                {state.latestBlock.actor}
              </p>
              <dl className={styles.hashes}>
                <div>
                  <dt>Хеш записи</dt>
                  <dd title={state.latestBlock.hash}>{shortHash(state.latestBlock.hash)}</dd>
                </div>
                <div>
                  <dt>Отпечаток документов</dt>
                  <dd title={state.latestBlock.documentDigest}>{shortHash(state.latestBlock.documentDigest)}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className={styles.empty}>Для этого груза пока нет записи в реестре — подайте комплект на проверку.</p>
          )}

          {state.recentBlocks.length > 0 && (
            <div className={styles.history}>
              <h3>Все попытки груза {shipmentId}</h3>
              <ol>
                {state.recentBlocks.map((block) => (
                  <li key={block.hash}>
                    <span className={styles.blockNumber}>#{block.index}</span>
                    <span>{decisionLabel(block.decision)}</span>
                    <code title={block.documentDigest}>{shortHash(block.documentDigest)}</code>
                    <span>{formatTime(block.createdAt)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {readOnly && (
            <p className={styles.footer}>
              Новые записи создаются кнопкой «Подать на предварительную проверку» выше.
            </p>
          )}
        </>
      )}
    </section>
  );
}
