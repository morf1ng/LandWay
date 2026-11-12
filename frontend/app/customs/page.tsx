"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, apiUpload, documentFileUrl } from "@/lib/api";
import { docStatusLabel } from "@/lib/labels";

type Document = {
  id: string;
  shipmentId: string;
  name: string;
  type: string;
  status: string;
  uploadedAt: string | null;
  comment: string;
  file: { storedName: string; originalName: string } | null;
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

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function CustomsInner() {
  const search = useSearchParams();
  const initialShipment = search.get("shipment") ?? "SCT-1004";
  const [documents, setDocuments] = useState<Document[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [shipmentId, setShipmentId] = useState(initialShipment);
  const [type, setType] = useState("declaration");
  const [file, setFile] = useState<File | null>(null);
  const [checkResult, setCheckResult] = useState<{ ready: boolean; problems: string[] } | null>(null);
  const [preclearResult, setPreclearResult] = useState<string>("");
  const [error, setError] = useState("");

  function reloadDocs() {
    apiGet<Document[]>("/documents").then(setDocuments);
    apiGet<JournalEntry[]>("/journal").then(setJournal);
  }

  useEffect(() => {
    reloadDocs();
    apiGet<Meta>("/meta").then(setMeta);
  }, []);

  useEffect(() => {
    setShipmentId(initialShipment);
  }, [initialShipment]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Выберите файл");
      return;
    }
    setError("");
    const form = new FormData();
    form.append("shipmentId", shipmentId);
    form.append("type", type);
    form.append("file", file);
    try {
      await apiUpload("/documents", form);
      setFile(null);
      reloadDocs();
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function checkDocs() {
    setError("");
    try {
      const result = await apiPost<{ ready: boolean; problems: string[] }>("/documents/check", { shipmentId });
      setCheckResult(result);
      reloadDocs();
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  async function preclear() {
    setError("");
    try {
      const result = await apiPost<{ status: string; details: string }>("/documents/preclear", { shipmentId });
      setPreclearResult(`${result.status}: ${result.details}`);
      reloadDocs();
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  const shipmentIds = Array.from(new Set(documents.map((d) => d.shipmentId)));

  return (
    <div className="appPage">
      <h1>Таможня и документы</h1>
      <p className="pageLead">Демонстрация предварительной проверки. Решение о выпуске принимает внешняя сторона.</p>
      {error && <p className="error">{error}</p>}

      <section>
        <h2>Общий список документов</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Груз</th>
              <th>Документ</th>
              <th>Тип</th>
              <th>Загружен</th>
              <th>Статус</th>
              <th>Комментарий</th>
              <th>Файл</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td>
                  <Link href={`/shipments/${d.shipmentId}`}>{d.shipmentId}</Link>
                </td>
                <td>{d.name}</td>
                <td>{meta?.documentTypes.find((item) => item.id === d.type)?.label ?? d.type}</td>
                <td>{formatDate(d.uploadedAt)}</td>
                <td>{docStatusLabel[d.status] ?? d.status}</td>
                <td>{d.comment}</td>
                <td>
                  {d.file ? (
                    <a href={documentFileUrl(d.id)} target="_blank" rel="noreferrer">
                      {d.file.originalName}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Загрузка документа</h2>
        <form onSubmit={onUpload}>
          <p>
            <label>
              Груз
              <br />
              <select value={shipmentId} onChange={(e) => setShipmentId(e.target.value)}>
                {shipmentIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          </p>
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
              <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
          </p>
          <button type="submit" className="primaryAction">Загрузить</button>
        </form>
      </section>

      <section>
        <h2>Проверка и предварительное оформление</h2>
        <p>
          Груз:{" "}
          <select value={shipmentId} onChange={(e) => setShipmentId(e.target.value)}>
            {shipmentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </p>
        <button type="button" onClick={checkDocs}>
          Проверить документы
        </button>{" "}
        <button type="button" className="primaryAction" onClick={preclear}>
          Отправить на предварительное оформление
        </button>
        {checkResult && (
          <div>
            <p>{checkResult.ready ? "Комплект готов" : "Есть проблемы"}</p>
            {checkResult.problems.length > 0 && (
              <ul>
                {checkResult.problems.map((p, i) => (
                  <li key={i}>
                    {p}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {preclearResult && <p>{preclearResult}</p>}
      </section>

      <section>
        <h2>Цифровой журнал событий</h2>
        <table>
          <thead>
            <tr>
              <th>Время</th>
              <th>Груз</th>
              <th>Событие</th>
              <th>Результат</th>
              <th>Детали</th>
            </tr>
          </thead>
          <tbody>
            {journal.map((j) => (
              <tr key={j.id}>
                <td>{formatDate(j.at)}</td>
                <td>{j.shipmentId}</td>
                <td>{j.title}</td>
                <td>{j.result}</td>
                <td>{j.details}</td>
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
