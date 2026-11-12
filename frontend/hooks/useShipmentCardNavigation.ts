"use client";

import { useCallback, useEffect, useState, type MouseEvent } from "react";
import { flushSync } from "react-dom";
import { useRouter } from "next/navigation";
import type { ShipmentCardData } from "@/lib/shipments/format";
import {
  clearSharedShipment,
  popScrollY,
  readSharedShipment,
  saveListPrefs,
  saveScrollY,
  setSharedShipment,
  type ShipmentListPrefs,
} from "@/lib/shipments/listStorage";
import { isPlainLeftClick, navigateWithViewTransition } from "@/lib/shipments/navigation";

export function useShipmentCardNavigation(fromList: "shipments" | "dashboard", prefs?: ShipmentListPrefs) {
  const router = useRouter();
  const [sharedId, setSharedId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      history.scrollRestoration = "manual";
    }
    const sid = readSharedShipment();
    if (sid) setSharedId(sid);
    const y = popScrollY();
    if (y > 0) {
      requestAnimationFrame(() => window.scrollTo(0, y));
    }
    const timer = window.setTimeout(() => clearSharedShipment(), 650);
    return () => window.clearTimeout(timer);
  }, []);

  const openCard = useCallback(
    (event: MouseEvent<HTMLAnchorElement>, item: ShipmentCardData) => {
      if (!isPlainLeftClick(event)) return;
      event.preventDefault();
      saveScrollY();
      if (prefs) saveListPrefs(prefs);
      setSharedShipment(item.id, fromList);
      const href = `/shipments/${encodeURIComponent(item.id)}`;
      const canShare = Boolean(document.getElementById(`list-${item.id}`));
      navigateWithViewTransition(
        router,
        href,
        "enter",
        () => {
          if (canShare) flushSync(() => setSharedId(item.id));
        },
        undefined
      );
    },
    [router, fromList, prefs]
  );

  return { sharedId, openCard };
}

export function useShipmentDetailNavigation(id: string) {
  const router = useRouter();
  const [shared, setShared] = useState(false);

  useEffect(() => {
    setShared(readSharedShipment() === id);
    const timer = window.setTimeout(() => clearSharedShipment(), 650);
    return () => window.clearTimeout(timer);
  }, [id]);

  const goBack = useCallback(
    (event: MouseEvent<HTMLAnchorElement>, href: string) => {
      if (!isPlainLeftClick(event)) return;
      event.preventDefault();
      setSharedShipment(id, href === "/" ? "dashboard" : "shipments");
      navigateWithViewTransition(router, href, "return", () => {
        flushSync(() => setShared(true));
      });
    },
    [router, id]
  );

  return { shared, goBack };
}
