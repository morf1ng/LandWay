type CoordPair = [number, number];

export type MapPlace = {
  name: string;
  lat: number;
  lon: number;
  kind: string;
  waitingShipments?: number;
  weather?: string;
  workload?: number;
  delayNote?: string;
};

export type MapShipment = {
  id: string;
  name: string;
  status: string;
  origin: string;
  destination: string;
  riskLevel: string;
  probability?: number;
  position: { lat: number; lon: number; name: string };
  stages: Array<{
    id?: string;
    location: string;
    nextLocation: string;
    transportType?: string;
    plannedArrival?: string;
    status?: string;
    description?: string;
    delayHours?: number;
  }>;
};

export function placeIndex(places: MapPlace[]) {
  const map = new Map<string, MapPlace>();
  for (const p of places) map.set(p.name, p);
  return map;
}

export function corridorBounds(places: MapPlace[]): CoordPair[] {
  if (!places.length) return [[42, 44], [52, 50]];
  const lats = places.map((p) => p.lat);
  const lons = places.map((p) => p.lon);
  const pad = 0.45;
  return [
    [Math.min(...lats) - pad, Math.min(...lons) - pad],
    [Math.max(...lats) + pad, Math.max(...lons) + pad],
  ];
}

export function routeSegments(
  stages: MapShipment["stages"],
  index: Map<string, MapPlace>
): Array<{ points: CoordPair[]; transport: string; status: string }> {
  const out: Array<{ points: CoordPair[]; transport: string; status: string }> = [];
  for (const stage of stages) {
    const from = index.get(stage.location);
    const to = index.get(stage.nextLocation);
    if (!from || !to) continue;
    out.push({
      points: [
        [from.lat, from.lon],
        [to.lat, to.lon],
      ],
      transport: String(stage.transportType ?? "road"),
      status: String(stage.status ?? ""),
    });
  }
  return out;
}

export function shipmentMarkerColor(status: string, riskLevel: string, selected: boolean) {
  if (selected) return "#4800ff";
  if (status === "delayed") return "#c45c10";
  if (status === "delivered") return "#276346";
  if (riskLevel === "high") return "#b42318";
  if (status === "in_transit") return "#6b4ce6";
  return "#4a4654";
}
