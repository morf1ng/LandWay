"use client";

import { useEffect, useState } from "react";
import { toShipmentCardData } from "@/lib/shipments/adapters";
import type { ShipmentCardData } from "@/lib/shipments/format";
import { useShipmentCardNavigation } from "@/hooks/useShipmentCardNavigation";
import { loadListPrefs, saveListPrefs, type ShipmentListPrefs } from "@/lib/shipments/listStorage";
import { ShipmentCard } from "./ShipmentCard";
import { ShipmentListRows } from "./ShipmentListRows";
import { ViewToggle, type ShipmentView } from "./ViewToggle";
import styles from "./shipmentCards.module.css";

type Props = {
  heading?: string;
  titleId?: string;
  items: ShipmentCardData[];
};

export function RecentShipments({ heading = "Последние перевозки", titleId, items }: Props) {
  const [view, setView] = useState<ShipmentView>("cards");
  const { sharedId, openCard } = useShipmentCardNavigation("dashboard");

  useEffect(() => {
    setView(loadListPrefs().view);
  }, []);

  function onViewChange(next: ShipmentView) {
    setView(next);
    const prefs: ShipmentListPrefs = { ...loadListPrefs(), view: next };
    saveListPrefs(prefs);
  }

  if (items.length === 0) {
    return (
      <>
        <SectionHeader heading={heading} titleId={titleId} view={view} onViewChange={onViewChange} />
        <p className={styles.emptyState}>Перевозок пока нет.</p>
      </>
    );
  }

  const hrefFor = (id: string) => `/shipments/${encodeURIComponent(id)}`;

  return (
    <>
      <div className={styles.sectionHead}>
        <h2 id={titleId}>{heading}</h2>
        <ViewToggle value={view} onChange={onViewChange} />
      </div>
      {view === "cards" ? (
        <div className={styles.cardGrid}>
          {items.map((row) => {
            const item = toShipmentCardData(row);
            return (
              <ShipmentCard
                key={item.id}
                item={item}
                href={hrefFor(item.id)}
                shared={sharedId === item.id}
                onActivate={openCard}
              />
            );
          })}
        </div>
      ) : (
        <ShipmentListRows items={items.map(toShipmentCardData)} hrefFor={hrefFor} onActivate={openCard} />
      )}
    </>
  );
}

function SectionHeader({
  heading,
  titleId,
  view,
  onViewChange,
}: {
  heading: string;
  titleId?: string;
  view: ShipmentView;
  onViewChange: (v: ShipmentView) => void;
}) {
  return (
    <div className={styles.sectionHead}>
      <h2 id={titleId}>{heading}</h2>
      <ViewToggle value={view} onChange={onViewChange} />
    </div>
  );
}
