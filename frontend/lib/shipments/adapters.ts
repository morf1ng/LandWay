import type { ShipmentCardData } from "./format";

type Row = {
  id: string;
  name: string;
  origin: string;
  destination: string;
  status: string;
  predictedArrival: string;
  riskLevel: string;
  probability: number;
};

export function toShipmentCardData(row: Row): ShipmentCardData {
  return {
    id: row.id,
    name: row.name,
    origin: row.origin,
    destination: row.destination,
    status: row.status,
    predictedArrival: row.predictedArrival,
    riskLevel: row.riskLevel,
    probability: row.probability,
  };
}
