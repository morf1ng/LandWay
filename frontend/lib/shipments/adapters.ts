import type { ShipmentCardData } from "./format";

type Row = {
  id: string;
  name: string;
  origin: string;
  destination: string;
  currentLocation?: string;
  status: string;
  predictedArrival: string | null;
  riskLevel: string;
  probability: number;
};

export function toShipmentCardData(row: Row): ShipmentCardData {
  return {
    id: row.id,
    name: row.name,
    origin: row.origin,
    destination: row.destination,
    currentLeg: row.currentLocation || undefined,
    status: row.status,
    predictedArrival: row.predictedArrival,
    riskLevel: row.riskLevel,
    probability: row.probability,
  };
}
