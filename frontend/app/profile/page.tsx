"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import styles from "./profile.module.css";

type Profile = {
  name: string;
  role: string;
  organization: string;
  username?: string;
  roleEditable?: boolean;
};

/** Поля профиля, которые редактируются как текст в форме. */
type EditableFieldKey = "name" | "role" | "organization";

function editableValue(profile: Profile, key: EditableFieldKey): string {
  return profile[key];
}

const FIELDS: { key: EditableFieldKey; label: string }[] = [
  { key: "name", label: "Имя" },
  { key: "role", label: "Роль" },
  { key: "organization", label: "Организация" },
];

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [editing, setEditing] = useState<EditableFieldKey | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGet<Profile>("/profile")
      .then(setProfile)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  async function commitField(key: EditableFieldKey) {
    if (!profile || !canEdit(key)) return;
    const value = draft.trim();
    if (!value) {
      setError(`Поле «${FIELDS.find((field) => field.key === key)?.label}» не может быть пустым`);
      return;
    }
    if (value === editableValue(profile, key)) {
      setEditing(null);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const patch: Partial<Pick<Profile, EditableFieldKey>> = { [key]: value };
      const saved = await apiPatch<Profile>("/profile", patch);
      setProfile(saved);
      setEditing(null);
      setOk("Сохранено");
      window.setTimeout(() => setOk(""), 2400);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setSaving(false);
    }
  }

  function canEdit(key: EditableFieldKey) {
    if (key !== "role") return true;
    if (profile?.roleEditable === false || profile?.username === "logist") return false;
    return true;
  }

  function startEdit(key: EditableFieldKey) {
    if (!profile || !canEdit(key)) return;
    setEditing(key);
    setDraft(editableValue(profile, key));
    setOk("");
    setError("");
  }

  if (!profile) return <p role="status">{error || "Загрузка профиля…"}</p>;

  return (
    <div className={styles.page}>
      <div className={styles.decor} aria-hidden="true">
        <span className={styles.topLeft} />
        <span className={styles.topDark} />
        <span className={styles.rightPurple} />
        <span className={styles.bottomLeft} />
        <span className={styles.bottomDark} />
      </div>
      <div className={styles.content}>
        <header className={styles.hero}>
          <img src="/landway-wordmark.svg" alt="LANDWAY" width={445} height={58} />
          <h1 className={styles.subtitle}>Профиль</h1>
        </header>

        <div className={styles.fields} aria-label="Данные профиля">
          {FIELDS.map(({ key, label }) => {
            const active = editing === key;
            return (
              <div key={key} className={styles.field}>
                <label htmlFor={`profile-${key}`} className={styles.fieldLabel}>{label}</label>
                <div className={styles.fieldBox}>
                  {active ? (
                    <input
                      id={`profile-${key}`}
                      className={styles.fieldInput}
                      value={draft}
                      autoFocus
                      maxLength={255}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitField(key);
                        if (e.key === "Escape") setEditing(null);
                      }}
                    />
                  ) : (
                    <span id={`profile-${key}`} className={styles.fieldValue}>{editableValue(profile, key)}</span>
                  )}
                  {canEdit(key) ? (
                    <button
                      type="button"
                      className={styles.editLink}
                      disabled={saving}
                      aria-label={active ? `Сохранить ${label.toLowerCase()}` : `Изменить ${label.toLowerCase()}`}
                      onClick={() => (active ? void commitField(key) : startEdit(key))}
                    >
                      {active ? "Сохранить" : "Изменить"}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        {error ? <p className={styles.error} role="alert">{error}</p> : null}
        {ok ? <p className={styles.toast} role="status">{ok}</p> : null}
      </div>
    </div>
  );
}
