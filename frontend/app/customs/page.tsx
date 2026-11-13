"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, FormEvent, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiUpload, documentFileUrl } from "@/lib/api";
import { docStatusLabel } from "@/lib/labels";
import { CorridorContract } from "./CorridorContract";
import { formatDateTime } from "@/lib/format";

type Document = {
  id: string;
  shipmentId: string;
  name: string;
  type: string;
  status: string;
  uploadedAt: string | null;
  comment: string;
  file: { storedName: string; originalName: string } | null;
  fields?: { number?: string; issuedAt?: string };
};

type JournalEntry = {
  id: string;
  shipmentId: string;
  title: string;
  result: string;
  details: string;
  at: string;
};

type Meta = {
  documentTypes: Array<{ id: string; label: string }>;
};

type ReviewResult = {
  statusLabel: string;
  preclearanceStatus?: string;
  problems: string[];
  submittedAt?: string;
  staleDecision?: boolean;
  staleMessage?: string | null;
  deduplicated?: boolean;
  createdBlock?: boolean;
  note?: string;
  shipmentBlockCount?: number;
};

function formatDate(value: string | null) {
  return formatDateTime(value);
}

function newIdempotencyKey() {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `idem-${Date.now()}`;
}

function CustomsInner() {
  const router = useRouter();
  const search = useSearchParams();
  const initialShipment = search.get("shipment") ?? "SCT-1004";
  const [documents, setDocuments] = useState<Document[]>([]);
  const [shipmentIds, setShipmentIds] = useState<string[]>([initialShipment]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [shipmentId, setShipmentId] = useState(initialShipment);
  const [type, setType] = useState("declaration");
  const [file, setFile] = useState<File | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [contractVersion, setContractVersion] = useState(0);
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(true);
  const [formKey, setFormKey] = useState(0);
  const idempotencyRef = useRef(newIdempotencyKey());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const shipmentIdRef = useRef(initialShipment);
  const reviewRequest = useRef(0);
  const docsRequest = useRef(0);
  const actionEpoch = useRef(0);
  shipmentIdRef.current = shipmentId;

  const shipmentDocs = documents.filter((d) => d.shipmentId === shipmentId);
  const shipmentJournal = journal.filter((j) => j.shipmentId === shipmentId && j.title.includes("Предварительн"));

  function reloadDocs() {
    const requestId = ++docsRequest.current;
    const epoch = actionEpoch.current;
    apiGet<Document[]>("/documents")
      .then((rows) => {
        if (requestId !== docsRequest.current) return;
        setDocuments(rows);
      })
      .catch((cause) => {
        if (requestId !== docsRequest.current || epoch !== actionEpoch.current) return;
        setError((cause as Error).message);
      });
    apiGet<JournalEntry[]>("/journal")
      .then((rows) => {
        if (requestId !== docsRequest.current) return;
        setJournal(rows);
      })
      .catch((cause) => {
        if (requestId !== docsRequest.current || epoch !== actionEpoch.current) return;
        setError((cause as Error).message);
      });
  }

  function startFix(doc: Document) {
    setType(doc.type);
    setNotice("");
    fileInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    fileInputRef.current?.focus();
  }

  function loadReviewState(id: string) {
    const requestId = ++reviewRequest.current;
    const epoch = actionEpoch.current;
    setReviewLoading(true);
    apiGet<ReviewResult>(`/documents/preliminary-review/${encodeURIComponent(id)}`)
      .then((state) => {
        if (requestId !== reviewRequest.current || epoch !== actionEpoch.current) return;
        setReviewResult({
          statusLabel: state.statusLabel || state.preclearanceStatus || "—",
          preclearanceStatus: state.preclearanceStatus,
          problems: state.problems || [],
          submittedAt: state.submittedAt,
          staleDecision: state.staleDecision,
          staleMessage: state.staleMessage,
          note: state.note,
          shipmentBlockCount: state.shipmentBlockCount,
        });
      })
      .catch(() => {
        if (requestId !== reviewRequest.current || epoch !== actionEpoch.current) return;
        setReviewResult(null);
      })
      .finally(() => {
        if (requestId !== reviewRequest.current || epoch !== actionEpoch.current) return;
        setReviewLoading(false);
      });
  }

  useEffect(() => {
    reloadDocs();
    apiGet<Meta>("/meta")
      .then(setMeta)
      .catch((cause) => setError((cause as Error).message));
    apiGet<Array<{ id: string; preclearanceStatus?: string }>>("/shipments")
      .then((shipments) => setShipmentIds(shipments.map((shipment) => shipment.id)))
      .catch((cause) => setError((cause as Error).message));
  }, []);

  useEffect(() => {
    if (initialShipment === shipmentIdRef.current) return;
    shipmentIdRef.current = initialShipment;
    reviewRequest.current += 1;
    actionEpoch.current += 1;
    setShipmentId(initialShipment);
    setReviewResult(null);
    setReviewLoading(true);
    setError("");
    setNotice("");
    setSubmitting(false);
    setUploading(false);
    idempotencyRef.current = newIdempotencyKey();
  }, [initialShipment]);

  useEffect(() => {
    if (shipmentId) loadReviewState(shipmentId);
  }, [shipmentId, contractVersion]);

  function selectShipment(id: string) {
    if (id === shipmentIdRef.current) return;
    shipmentIdRef.current = id;
    reviewRequest.current += 1;
    actionEpoch.current += 1;
    setShipmentId(id);
    setReviewResult(null);
    setReviewLoading(true);
    setError("");
    setNotice("");
    setSubmitting(false);
    setUploading(false);
    idempotencyRef.current = newIdempotencyKey();
    router.replace(`/customs?shipment=${encodeURIComponent(id)}`, { scroll: false });
  }

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Выберите файл");
      return;
    }
    const id = shipmentIdRef.current;
    const epoch = ++actionEpoch.current;
    reviewRequest.current += 1;
    setError("");
    setNotice("");
    setUploading(true);
    const hadDecision = Boolean(reviewResult?.submittedAt);
    const form = new FormData();
    form.append("shipmentId", id);
    form.append("type", type);
    form.append("file", file);
    try {
      await apiUpload("/documents", form);
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      setFile(null);
      setFormKey((value) => value + 1);
      reloadDocs();
      idempotencyRef.current = newIdempotencyKey();
      setContractVersion((value) => value + 1);
      const label = meta?.documentTypes.find((item) => item.id === type)?.label ?? type;
      setNotice(
        hadDecision
          ? `Файл «${label}» загружен. Прежнее решение относится к старой версии комплекта — подайте комплект повторно.`
          : `Файл «${label}» загружен. Теперь можно подать комплект на предварительную проверку.`
      );
    } catch (err) {
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      setError(String((err as Error).message));
    } finally {
      if (epoch === actionEpoch.current && shipmentIdRef.current === id) setUploading(false);
    }
  }

  async function submitForReview() {
    const id = shipmentIdRef.current;
    const epoch = ++actionEpoch.current;
    const idempotencyKey = idempotencyRef.current;
    reviewRequest.current += 1;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const result = await apiPost<ReviewResult>("/documents/preliminary-review", {
        shipmentId: id,
        idempotencyKey,
      });
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      setReviewResult(result);
      reloadDocs();
      setContractVersion((value) => value + 1);
      if (result.createdBlock !== false) {
        idempotencyRef.current = newIdempotencyKey();
      }
    } catch (err) {
      if (epoch !== actionEpoch.current || shipmentIdRef.current !== id) return;
      setError(String((err as Error).message));
    } finally {
      if (epoch === actionEpoch.current && shipmentIdRef.current === id) setSubmitting(false);
    }
  }

  return (
    <div className="appPage">
      <h1>Таможня и документы</h1>
      <p className="pageLead">
        Демонстрационная предварительная проверка комплекта. Решение имитирует проверяющую сторону,
        не заменяет таможню.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="successMessage" role="status">
          {notice}
        </p>
      )}

      <section>
        <h2>Комплект груза {shipmentId}</h2>
        <p>
          <label className="fieldInline">
          Груз{" "}
          <select value={shipmentId} onChange={(e) => selectShipment(e.target.value)}>
            {shipmentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          </label>
        </p>

        <div className="customsReviewBanner" data-stale={reviewResult?.staleDecision ? true : undefined}>
          <span className="demoTag">Демо-проверка</span>{" "}
          <strong>Статус предварительной проверки:</strong>{" "}
          {reviewLoading
            ? "Загружаем статус…"
            : (reviewResult?.preclearanceStatus ?? reviewResult?.statusLabel ?? "Ещё не подавали")}
          {reviewResult?.staleDecision ? " — устарело, комплект изменён после проверки" : ""}
          {reviewResult?.submittedAt && (
            <span className="muted"> · {formatDate(reviewResult.submittedAt)}</span>
          )}
          {reviewResult?.staleDecision && reviewResult.staleMessage && (
            <p className="error" role="alert">
              {reviewResult.staleMessage}
            </p>
          )}
        </div>

        <button type="button" className="primaryAction" disabled={submitting} onClick={submitForReview}>
          {submitting ? "Подаём комплект…" : "Подать на предварительную проверку"}
        </button>
        <p className="muted">
          Одно действие: проверка обязательных документов, замечания, запись в реестр и обновление статуса груза.
        </p>

        {reviewResult && reviewResult.problems.length > 0 && (
          <div className="customsProblems">
            <strong>Замечания по комплекту</strong>
            <ul>
              {reviewResult.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
        {reviewResult?.statusLabel === "Готов к рассмотрению" && !reviewResult.staleDecision && (
          <p className="muted">Комплект прошёл демо-проверку. Статус «Готов к рассмотрению» совпадает в карточке груза.</p>
        )}

        <table className="stackedTable">
          <thead>
            <tr>
              <th>Документ</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Комментарий</th>
              <th>Файл</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            {shipmentDocs.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  Для груза ещё нет документов — загрузите их ниже.
                </td>
              </tr>
            )}
            {shipmentDocs.map((d) => (
              <tr key={d.id}>
                <td data-label="Документ">{d.name}</td>
                <td data-label="Тип">{meta?.documentTypes.find((item) => item.id === d.type)?.label ?? d.type}</td>
                <td data-label="Статус">{docStatusLabel[d.status] ?? d.status}</td>
                <td data-label="Комментарий">{d.comment || "—"}</td>
                <td data-label="Файл">
                  {d.file ? (
                    <a href={documentFileUrl(d.id)} target="_blank" rel="noreferrer">
                      {d.file.originalName}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
                <td data-label="Действие">
                  {d.status === "verified" ? (
                    <span className="muted">—</span>
                  ) : (
                    <button type="button" onClick={() => startFix(d)}>
                      {d.file ? "Заменить файл" : "Загрузить файл"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          <Link className="button-link" href={`/shipments/${shipmentId}`}>
            Открыть карточку груза →
          </Link>
        </p>
      </section>

      <section>
        <h2>Загрузка и исправление документа</h2>
        <form onSubmit={onUpload} key={formKey}>
          <p>
            <label>
              Тип
              <br />
              <select value={type} onChange={(e) => setType(e.target.value)}>
                {meta?.documentTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <p>
            <label>
              Файл
              <br />
              <input ref={fileInputRef} type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
          </p>
          <button type="submit" className="primaryAction" disabled={uploading}>
            {uploading ? "Загружаем…" : "Загрузить / заменить файл"}
          </button>
        </form>
      </section>

      <CorridorContract
        key={shipmentId}
        shipmentId={shipmentId}
        shipmentIds={shipmentIds}
        onShipmentChange={selectShipment}
        version={contractVersion}
        readOnly
      />

      <section>
        <h2>История попыток проверки · {shipmentId}</h2>
        {shipmentJournal.length === 0 ? (
          <p className="muted">Попыток пока нет.</p>
        ) : (
          <table className="stackedTable">
            <thead>
              <tr>
                <th>Время</th>
                <th>Решение</th>
                <th>Детали</th>
              </tr>
            </thead>
            <tbody>
              {shipmentJournal.map((j) => (
                <tr key={j.id}>
                  <td data-label="Время">{formatDate(j.at)}</td>
                  <td data-label="Решение">{j.result}</td>
                  <td data-label="Детали">{j.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>Общий список документов</h2>
        <table className="stackedTable">
          <thead>
            <tr>
              <th>ID</th>
              <th>Груз</th>
              <th>Документ</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td data-label="ID">{d.id}</td>
                <td data-label="Груз">
                  <Link href={`/shipments/${d.shipmentId}`}>{d.shipmentId}</Link>
                </td>
                <td data-label="Документ">{d.name}</td>
                <td data-label="Статус">{docStatusLabel[d.status] ?? d.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default function CustomsPage() {
  return (
    <Suspense fallback={<p>Загрузка…</p>}>
      <CustomsInner />
    </Suspense>
  );
}
