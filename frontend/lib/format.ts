/** Сервер хранит время без смещения в часовом поясе МСК — показываем его в МСК независимо от браузера. */

export const TIME_ZONE = "Europe/Moscow";

export function parseServerDate(value?: string | null): Date | null {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  const date = new Date(hasZone ? value : `${value}+03:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value?: string | null, withZone = false): string {
  const date = parseServerDate(value);
  if (!date) return value || "—";
  const text = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(date);
  return withZone ? `${text} МСК` : text;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("ru-RU", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function formatRub(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${formatNumber(Math.round(value))} ₽`;
}

export function formatKgCo2(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${formatNumber(value, 1)} кг CO₂`;
}

export function formatHours(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${formatNumber(value, 1)} ч`;
}

export function signed(value: number | null | undefined, format: (v: number) => string): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) < 0.05) return "без изменений";
  return `${value > 0 ? "+" : "−"}${format(Math.abs(value))}`;
}
