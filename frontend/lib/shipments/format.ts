/** Поля карточки груза (адаптер к API). */

export type ShipmentCardData = {
  id: string;
  name: string;
  origin: string;
  destination: string;
  currentLeg?: string;
  status: string;
  predictedArrival: string | null;
  riskLevel: string;
  probability: number;
};

import { parseServerDate, TIME_ZONE as TZ } from "@/lib/format";

export function formatArrivalRu(value?: string | null): string {
  if (!value) return "не определён";
  const date = parseServerDate(value);
  if (!date) return "не определён";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TZ,
  }).format(date);
}

export function shipmentCardAriaLabel(row: ShipmentCardData, statusText: string, riskText: string): string {
  return `${row.id}, ${row.name}. Маршрут ${row.origin} — ${row.destination}. Статус: ${statusText}. Прогноз: ${formatArrivalRu(
    row.predictedArrival
  )} МСК. Риск: ${riskText}, ${row.probability} процентов. Открыть подробности`;
}
