"use client";

import { logoutRequest } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function LogoutPage() {
  const router = useRouter();
  const [done, setDone] = useState(false);

  useEffect(() => {
    logoutRequest().then(() => {
      setDone(true);
      router.replace("/login");
    });
  }, [router]);

  return (
    <>
      <h1>Выход</h1>
      <p>{done ? "Сессия завершена, перенаправление…" : "Завершение сессии…"}</p>
      <p>
        <Link href="/login">Страница входа</Link>
      </p>
    </>
  );
}
