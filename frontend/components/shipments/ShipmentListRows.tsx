"use client";

import { riskLabel, statusLabel } from "@/lib/labels";
import { formatArrivalRu, shipmentCardAriaLabel, type ShipmentCardData } from "@/lib/shipments/format";
import type { MouseEvent } from "react";
import styles from "./shipmentCards.module.css";

type Props = {
  items: ShipmentCardData[];
  hrefFor: (id: string) => string;
  onActivate: (event: MouseEvent<HTMLAnchorElement>, item: ShipmentCardData) => void;
};

export function ShipmentListRows({ items, hrefFor, onActivate }: Props) {
  return (
    <ul className={styles.compactList}>
      {items.map((item) => {
        const statusText = statusLabel[item.status] ?? item.status;
        const riskText = riskLabel[item.riskLevel] ?? item.riskLevel;
        return (
          <li key={item.id}>
            <a
              id={`list-${item.id}`}
              className={styles.compactRow}
              href={hrefFor(item.id)}
              onClick={(event) => onActivate(event, item)}
              aria-label={shipmentCardAriaLabel(item, statusText, riskText)}
            >
              <span className={styles.compactId}>{item.id}</span>
              <span className={styles.compactRoute}>
                {item.origin} → {item.destination}
              </span>
              <span className={styles.compactName}>{item.name}</span>
              <span className={styles.status} data-status={item.status}>
                {statusText}
              </span>
              <span className={`${styles.compactMeta} ${styles.compactForecast}`}>
                <small>Прогноз (МСК)</small>
                <b>{formatArrivalRu(item.predictedArrival)}</b>
              </span>
              <span className={`${styles.compactMeta} ${styles.compactRisk}`}>
                <small>Риск</small>
                <b>
                  {riskText} · {item.probability}%
                </b>
              </span>
            </a>
          </li>
        );
      })}
    </ul>
  );
}
