"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";

type Profile = { name: string; role: string; organization: string };

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    apiGet<Profile>("/profile")
      .then(setProfile)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!profile) return;
    try {
      const saved = await apiPatch<Profile>("/profile", profile);
      setProfile(saved);
      setOk("Профиль сохранён (данные в общем хранилище).");
    } catch (err) {
      setError(String((err as Error).message));
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!profile) return <p>Загрузка…</p>;

  return (
    <div className="appPage">
      <h1>Профиль пользователя</h1>
      <section>
        <h2>Данные демологиста</h2>
        <form onSubmit={onSave} className="formGrid">
          <label>
            Имя
            <input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
          </label>
          <label>
            Роль
            <input value={profile.role} onChange={(e) => setProfile({ ...profile, role: e.target.value })} />
          </label>
          <label>
            Организация
            <input
              value={profile.organization}
              onChange={(e) => setProfile({ ...profile, organization: e.target.value })}
            />
          </label>
          <button type="submit" className="primaryAction">Сохранить</button>
        </form>
        {ok && <p className="successMessage">{ok}</p>}
      </section>
    </div>
  );
}
