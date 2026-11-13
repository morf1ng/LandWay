import { apiGet } from "@/lib/api";

export type InfrastructurePort = {
  name: string;
  workload?: number;
  waitingShipments?: number;
  delayNote?: string;
  departureStatus?: "open" | "departure_closed";
  restrictionStartsAt?: string | null;
  restrictionEndsAt?: string | null;
  restrictionNote?: string | null;
  sourceKind?: "live" | "demo" | "simulation";
  sourceName?: string;
  observedAt?: string;
};

export type InfrastructureRailStatus = {
  from: string;
  to: string;
  workload?: number;
  delayMinutes?: number;
  sourceKind?: "live" | "demo" | "simulation";
  sourceName: string;
  observedAt: string;
};

export type InfrastructureSnapshot = {
  ports: InfrastructurePort[];
  rail: InfrastructureRailStatus[];
  externalConnected?: boolean;
  lastUpdatedAt?: string;
};

export type InfrastructureStage = {
  location: string;
  nextLocation: string;
  transportType?: string;
  status?: string;
  delayHours?: number;
};

export type RouteInfrastructure = {
  ports: InfrastructurePort[];
  rail: InfrastructureStage[];
};

/** Оперативный статус инфраструктуры (opt-out через NEXT_PUBLIC_INFRASTRUCTURE_STATUS_ENABLED=false). */
export async function loadLiveInfrastructure(): Promise<InfrastructureSnapshot | null> {
  if (process.env.NEXT_PUBLIC_INFRASTRUCTURE_STATUS_ENABLED === "false") return null;
  try {
    return await apiGet<InfrastructureSnapshot>("/infrastructure/status");
  } catch {
    return null;
  }
}

/** Only infrastructure touched by the selected route is shown. */
export function infrastructureForRoute(
  stages: InfrastructureStage[],
  ports: InfrastructurePort[],
): RouteInfrastructure {
  const portByName = new Map(ports.map((port) => [port.name, port]));
  const routePortNames = new Set<string>();
  for (const stage of stages) {
    if (stage.transportType !== "sea") continue;
    if (portByName.has(stage.location)) routePortNames.add(stage.location);
    if (portByName.has(stage.nextLocation)) routePortNames.add(stage.nextLocation);
  }
  return {
    ports: Array.from(routePortNames).map((name) => portByName.get(name)!),
    rail: stages.filter((stage) => stage.transportType === "rail"),
  };
}
