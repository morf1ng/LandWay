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
    <>
      <h1>Уведомления</h1>
      <button type="button" onClick={readAll}>
        Отметить все прочитанными
      </button>
      <ul>
        {items.map((n) => (
          <li key={n.id} style={{ opacity: n.read ? 0.6 : 1 }}>
            [{n.severity}] {n.createdAt} —{" "}
            <Link href={n.href} onClick={() => readOne(n.id)}>
              {n.title}
            </Link>
            : {n.description}
          </li>
        ))}
      </ul>
    </>
  );
}
