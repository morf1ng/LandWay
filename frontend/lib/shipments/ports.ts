/** Координаты портов и узлов коридора (синхронно с backend/app/catalog.py). */

export type PortCoord = { lat: number; lon: number; x: number; y: number };

const PLACES: Record<string, PortCoord> = {
  Астрахань: { lat: 46.35, lon: 48.04, x: 48, y: 18 },
  Махачкала: { lat: 42.98, lon: 47.5, x: 40, y: 42 },
  Энзели: { lat: 37.47, lon: 49.46, x: 56, y: 76 },
  Амирабад: { lat: 36.85, lon: 53.37, x: 82, y: 82 },
  Саратов: { lat: 51.53, lon: 46.03, x: 46, y: 7 },
  Волгоград: { lat: 48.71, lon: 44.51, x: 30, y: 12 },
  Каспийск: { lat: 42.88, lon: 47.64, x: 37, y: 46 },
};

export function portPoint(name: string): PortCoord | null {
  if (PLACES[name]) return PLACES[name];
  for (const key of Object.keys(PLACES)) {
    if (name.includes(key) || key.includes(name)) return PLACES[key];
  }
  return null;
}

export function portLatLng(name: string): [number, number] | null {
  const p = portPoint(name);
  return p ? [p.lat, p.lon] : null;
}
