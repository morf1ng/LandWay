export type ShipmentListPrefs = {
  search: string;
  status: string;
  risk: string;
  origin: string;
  destination: string;
  transport: string;
  deliveryBefore: string;
  view: "cards" | "list";
};

export const defaultListPrefs: ShipmentListPrefs = {
  search: "",
  status: "",
  risk: "",
  origin: "",
  destination: "",
  transport: "",
  deliveryBefore: "",
  view: "cards",
};

function normalizeView(raw: unknown): "cards" | "list" {
  if (raw === "list" || raw === "table") return "list";
  return "cards";
}

const PREFS_KEY = "sct:shipments:prefs";
export function loadListPrefs(): ShipmentListPrefs {
  try {
    const raw = sessionStorage.getItem(PREFS_KEY);
    if (!raw) return defaultListPrefs;
    const merged = { ...defaultListPrefs, ...JSON.parse(raw) };
    merged.view = normalizeView(merged.view);
    return merged;
  } catch {
    return defaultListPrefs;
  }
}

export function saveListPrefs(prefs: ShipmentListPrefs) {
  try {
    sessionStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}
