"use client";

import { riskLabel, statusLabel } from "@/lib/labels";
import { formatArrivalRu, shipmentCardAriaLabel, type ShipmentCardData } from "@/lib/shipments/format";
import type { MouseEvent } from "react";
import { RoutePreview } from "./RoutePreview";
import styles from "./shipmentCards.module.css";

type Props = {
  item: ShipmentCardData;
  href: string;
  shared?: boolean;
  onActivate: (event: MouseEvent<HTMLAnchorElement>, item: ShipmentCardData) => void;
};

export function ShipmentCard({ item, href, shared, onActivate }: Props) {
  const statusText = statusLabel[item.status] ?? item.status;
  const riskText = riskLabel[item.riskLevel] ?? item.riskLevel;

  return (
    <a
      id={`list-${item.id}`}
      className={styles.shipmentCard}
      href={href}
      data-shared-shell={shared ? true : undefined}
      aria-label={shipmentCardAriaLabel(item, statusText, riskText)}
      onClick={(event) => onActivate(event, item)}
    >
      <RoutePreview origin={item.origin} destination={item.destination} sharedMap={shared} />
      <div className={styles.cardBody}>
        <div className={styles.cardTop}>
          <span className={styles.shipmentId}>{item.id}</span>
          <span className={styles.status} data-status={item.status}>
            {statusText}
          </span>
        </div>
        <strong className={styles.shipmentRoute}>
          {item.origin} <span aria-hidden="true">→</span> {item.destination}
        </strong>
        <span className={styles.cargoName}>{item.name}</span>
        <div className={styles.cardBottom}>
          <span>
            <small>Прогноз доставки (МСК)</small>
            <b>{formatArrivalRu(item.predictedArrival)}</b>
          </span>
          <span>
            <small>Риск</small>
            <b>
              {riskText} · {item.probability}%
            </b>
          </span>
        </div>
      </div>
    </a>
  );
}
