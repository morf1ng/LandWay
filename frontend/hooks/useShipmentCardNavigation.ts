"use client";

import { useLayoutEffect, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import type { ShipmentCardData } from "@/lib/shipments/format";
import { saveListPrefs, type ShipmentListPrefs } from "@/lib/shipments/listStorage";
import {
  getReturningCard,
  getShipmentOrigin,
  isNavigationLocked,
  isPlainLeftClick,
  linkShipmentHistory,
  navigateWithViewTransition,
  rememberShipmentOrigin,
  restoreShipmentOrigin,
  type ShipmentListHref,
} from "@/lib/shipments/navigation";

export function useShipmentCardNavigation(href: ShipmentListHref, ready: boolean, prefs?: ShipmentListPrefs) {
  const router = useRouter();

  useLayoutEffect(() => {
    if (ready) restoreShipmentOrigin(href);
  }, [href, ready]);

  function openCard(event: MouseEvent<HTMLAnchorElement>, item: ShipmentCardData) {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    if (isNavigationLocked()) return;

    if (prefs) saveListPrefs(prefs);
    rememberShipmentOrigin(item, href);
    const detailHref = event.currentTarget.pathname;
    const source = event.currentTarget.matches("[data-shipment-card]") ? event.currentTarget : null;
    void navigateWithViewTransition({
      source,
      destination: () => {
        const map = document.getElementById(`detail-map-${item.id}`);
        if (map) window.scrollTo({ top: 0, behavior: "instant" });
        return map;
      },
      mode: "enter",
      navigate: () => router.push(detailHref),
    });
  }

  return { openCard, returningId: getReturningCard(href) };
}

export function useShipmentDetailNavigation(id: string) {
  const router = useRouter();
  const origin = getShipmentOrigin(id);
  const backHref = origin?.href ?? "/shipments";

  useLayoutEffect(() => {
    if (origin) linkShipmentHistory(id);
  }, [id, origin]);

  function goBack(event: MouseEvent<HTMLAnchorElement>) {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    if (isNavigationLocked()) return;

    if (!origin) {
      router.push(backHref);
      return;
    }

    void navigateWithViewTransition({
      source: document.getElementById(`detail-map-${id}`),
      destination: () => {
        const card = document.getElementById(`list-${id}`);
        return card?.matches("[data-shipment-card]") ? card : null;
      },
      mode: "return",
      navigate: () => router.back(),
    });
  }

  return { preview: origin?.item, backHref, goBack };
}
