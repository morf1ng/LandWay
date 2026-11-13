import type { MouseEvent } from "react";
import type { ShipmentCardData } from "./format";

export type ShipmentListHref = "/" | "/shipments";

type ShipmentOrigin = {
  item: ShipmentCardData;
  href: ShipmentListHref;
  scrollY: number;
  needsRestore: boolean;
  pending: boolean;
};

let origin: ShipmentOrigin | undefined;
let navigating = false;

export function isPlainLeftClick(event: MouseEvent) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

export function rememberShipmentOrigin(item: ShipmentCardData, href: ShipmentListHref) {
  origin = { item, href, scrollY: window.scrollY, needsRestore: true, pending: true };
}

export function getShipmentOrigin(id: string) {
  if (typeof window === "undefined" || origin?.item.id !== id) return undefined;
  if (origin.pending || history.state?.landwayShipmentOrigin === id) return origin;
}

export function linkShipmentHistory(id: string) {
  if (origin?.item.id !== id) return;
  origin.needsRestore = true;
  if (!origin.pending) return;
  origin.pending = false;
  history.replaceState({ ...history.state, landwayShipmentOrigin: id }, "");
}

export function getReturningCard(href: ShipmentListHref) {
  return origin?.href === href && origin.needsRestore ? origin.item.id : undefined;
}

export function restoreShipmentOrigin(href: ShipmentListHref) {
  if (!origin?.needsRestore || origin.href !== href || location.pathname !== href) return;
  origin.needsRestore = false;
  window.scrollTo({ top: origin.scrollY, behavior: "instant" });
  document.getElementById(`list-${origin.item.id}`)?.focus({ preventScroll: true });
}

export function isNavigationLocked() {
  return navigating;
}

type SharedElements = { shell: HTMLElement; map: HTMLElement };

function sharedElements(shell: HTMLElement | null): SharedElements | null {
  const map = shell?.querySelector<HTMLElement>("[data-shipment-map]");
  return shell && map ? { shell, map } : null;
}

function isVisible(element: HTMLElement) {
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight &&
    rect.right > 0 && rect.left < window.innerWidth;
}

function waitForDestination(find: () => SharedElements | null, navigate: () => void) {
  return new Promise<SharedElements | null>((resolve, reject) => {
    const cleanup = () => {
      observer.disconnect();
      window.clearTimeout(timeout);
    };
    const check = () => {
      const target = find();
      if (!target) return;
      cleanup();
      resolve(target);
    };
    // Rendering is suspended during the native update callback, so use DOM commits as the signal.
    const observer = new MutationObserver(check);
    observer.observe(document.body, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => {
      cleanup();
      resolve(null);
    }, 850);
    try {
      navigate();
      check();
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}

function markShared({ shell, map }: SharedElements, cleanups: Array<() => void>) {
  shell.dataset.sharedShell = "";
  map.dataset.sharedMap = "";
  cleanups.push(() => {
    delete shell.dataset.sharedShell;
    delete map.dataset.sharedMap;
  });
}

function snapshot(element: HTMLElement, isShell: boolean) {
  const rect = element.getBoundingClientRect();
  const copy = element.cloneNode(true) as HTMLElement;
  if (isShell) copy.querySelector<HTMLElement>("[data-shipment-map]")!.style.visibility = "hidden";
  copy.removeAttribute("id");
  copy.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
  copy.setAttribute("aria-hidden", "true");
  copy.inert = true;
  copy.classList.add("shipment-snapshot");
  Object.assign(copy.style, {
    position: "fixed",
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    margin: "0",
    transform: "none",
    transformOrigin: "top left",
    zIndex: isShell ? "90" : "91",
    pointerEvents: "none",
  });
  return { copy, rect };
}

async function animateFallback(source: SharedElements, find: () => SharedElements | null, navigate: () => void) {
  const shell = snapshot(source.shell, true);
  const map = snapshot(source.map, false);
  const target = await waitForDestination(find, navigate);
  if (!target || !isVisible(target.shell)) return;

  const animate = ({ copy, rect }: ReturnType<typeof snapshot>, destination: HTMLElement) => {
    const end = destination.getBoundingClientRect();
    const transform = `translate(${end.left - rect.left}px, ${end.top - rect.top}px) scale(${end.width / rect.width}, ${end.height / rect.height})`;
    document.body.append(copy);
    return copy.animate(
      [{ transform: "none" }, { transform, opacity: 1, offset: 0.76 }, { transform, opacity: 0 }],
      { duration: 550, easing: "cubic-bezier(0.22, 0.82, 0.24, 1)", fill: "both" }
    );
  };

  const targets = [target.shell, target.map];
  targets.forEach((element) => element.classList.add("shipment-snapshot-target"));
  try {
    const animations = [animate(shell, target.shell), animate(map, target.map)];
    targets.forEach((element) => {
      animations.push(element.animate([{ opacity: 0 }, { opacity: 0, offset: 0.55 }, { opacity: 1 }], { duration: 550 }));
    });
    await Promise.allSettled(animations.map((animation) => animation.finished));
  } finally {
    targets.forEach((element) => element.classList.remove("shipment-snapshot-target"));
    shell.copy.remove();
    map.copy.remove();
  }
}

export async function navigateWithViewTransition({
  source,
  destination,
  mode,
  navigate,
}: {
  source: HTMLElement | null;
  destination: () => HTMLElement | null;
  mode: "enter" | "return";
  navigate: () => void;
}) {
  const from = sharedElements(source);
  if (!from || !isVisible(from.shell) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    navigate();
    return;
  }

  const root = document.documentElement;
  const cleanups: Array<() => void> = [];
  const find = () => sharedElements(destination());
  let requested = false;
  const requestNavigation = () => {
    if (requested) return;
    requested = true;
    navigate();
  };
  const reveal = () => {
    if (mode === "enter") root.dataset.shipmentReveal = "";
  };

  navigating = true;
  try {
    if (!document.startViewTransition) {
      reveal();
      await animateFallback(from, find, requestNavigation);
      return;
    }

    root.dataset.shipmentTransition = "native";
    markShared(from, cleanups);
    const transition = document.startViewTransition(async () => {
      const target = await waitForDestination(find, requestNavigation);
      // Next commits asynchronously. The second snapshot needs the mounted route and its map.
      if (!target || !isVisible(target.shell)) {
        transition.skipTransition();
        return;
      }
      cleanups.shift()?.();
      markShared(target, cleanups);
      reveal();
    });
    void transition.ready.catch(() => undefined);
    await transition.finished;
  } catch {
    requestNavigation();
  } finally {
    cleanups.forEach((cleanup) => cleanup());
    delete root.dataset.shipmentReveal;
    delete root.dataset.shipmentTransition;
    navigating = false;
  }
}
