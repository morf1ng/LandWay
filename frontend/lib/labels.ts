export const statusLabel: Record<string, string> = {
  awaiting: "Ожидает отправления",
  in_transit: "В пути",
  delayed: "Задерживается",
  documents_issue: "Проверка документов",
  delivered: "Доставлен",
};

export const riskLabel: Record<string, string> = {
  none: "—",
  low: "низкий",
  medium: "средний",
  high: "высокий",
};

export const transportLabel: Record<string, string> = {
  rail: "поезд",
  sea: "корабль",
  road: "грузовик",
  none: "—",
};

export const docStatusLabel: Record<string, string> = {
  verified: "проверен",
  needs_attention: "требует внимания",
  missing: "отсутствует",
  pending: "ожидает проверки",
};
