/** Поля карточки груза (адаптер к API). */

export type ShipmentCardData = {
  id: string;
  name: string;
  origin: string;
  destination: string;
  status: string;
  predictedArrival: string;
  riskLevel: string;
  probability: number;
};

const TZ = "Europe/Moscow";

export function formatArrivalRu(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
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
