import { portLatLng } from "./ports";

type Stage = { location: string; nextLocation: string; transportType?: string };

export function buildRouteGeometry(
  origin: string,
  destination: string,
  stages?: Stage[]
): { points: [number, number][]; lines: [number, number][][]; names: string[]; modes: string[] } {
  const points: [number, number][] = [];
  const lines: [number, number][][] = [];
  const names: string[] = [];
  const modes: string[] = [];

  const pushPoint = (name: string) => {
    const c = portLatLng(name);
    if (!c) return;
    if (!points.some(([lat, lon]) => lat === c[0] && lon === c[1])) {
      points.push(c);
      names.push(name);
    }
  };

  if (stages?.length) {
    for (const stage of stages) {
      const from = portLatLng(stage.location);
      const to = portLatLng(stage.nextLocation);
      if (from && to) {
        lines.push([from, to]);
        modes.push(stage.transportType ?? "road");
      }
      pushPoint(stage.location);
      pushPoint(stage.nextLocation);
    }
  } else {
    const from = portLatLng(origin);
    const to = portLatLng(destination);
    if (from && to) {
      lines.push([from, to]);
      modes.push("sea");
    }
    pushPoint(origin);
    pushPoint(destination);
  }

  return { points, lines, names, modes };
}
