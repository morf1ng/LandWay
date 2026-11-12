"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Notification = {
  id: string;
  title: string;
  description: string;
  severity: string;
  createdAt: string;
  read: boolean;
  href: string;
};

const severityLabel: Record<string, string> = { high: "Высокий риск", medium: "Внимание", low: "Информация" };

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [error, setError] = useState("");

  function load() {
    apiGet<Notification[]>("/notifications")
      .then(setItems)
      .catch((e) => setError(String(e.message || e)));
  }

  useEffect(() => {
    load();
  }, []);

  async function readAll() {
    await apiPost("/notifications/read-all", {});
    load();
  }

  async function readOne(id: string) {
    await apiPost(`/notifications/${id}/read`, {});
    load();
  }

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="appPage">
      <h1>Уведомления</h1>
      <div className="actionRow">
        <span className="muted">Непрочитанных: {items.filter((item) => !item.read).length}</span>
        <button type="button" onClick={readAll} disabled={!items.some((item) => !item.read)}>
          Отметить все прочитанными
        </button>
      </div>
      <section>
        <h2>События по грузам</h2>
        {items.length === 0 ? <p className="muted">Новых событий пока нет.</p> : (
          <ul className="notificationList">
            {items.map((n) => (
              <li key={n.id} className="notificationItem" data-read={n.read}>
                <div className="notificationMeta">
                  <span className="notificationSeverity" data-severity={n.severity}>{severityLabel[n.severity] ?? "Событие"}</span>
                  <time>{new Date(n.createdAt).toLocaleString("ru-RU")}</time>
                </div>
                <Link href={n.href} onClick={() => readOne(n.id)}>{n.title} →</Link>
                <span>{n.description}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
