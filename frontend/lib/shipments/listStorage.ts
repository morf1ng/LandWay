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
const SCROLL_KEY = "sct:scroll";
const SHARED_KEY = "sct:sharedId";
const FROM_KEY = "sct:fromList";

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

export function saveScrollY() {
  try {
    sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
  } catch {
    /* ignore */
  }
}

export function popScrollY(): number {
  try {
    const v = Number(sessionStorage.getItem(SCROLL_KEY) ?? 0) || 0;
    sessionStorage.removeItem(SCROLL_KEY);
    return v;
  } catch {
    return 0;
  }
}

export function setSharedShipment(id: string, fromList: "shipments" | "dashboard") {
  try {
    sessionStorage.setItem(SHARED_KEY, id);
    sessionStorage.setItem(FROM_KEY, fromList);
  } catch {
    /* ignore */
  }
}

export function readSharedShipment(): string | null {
  try {
    return sessionStorage.getItem(SHARED_KEY);
  } catch {
    return null;
  }
}

export function clearSharedShipment() {
  try {
    sessionStorage.removeItem(SHARED_KEY);
  } catch {
    /* ignore */
  }
}

export function readReturnHref(): string {
  try {
    const from = sessionStorage.getItem(FROM_KEY);
    return from === "dashboard" ? "/" : "/shipments";
  } catch {
    return "/shipments";
  }
}
