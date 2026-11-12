import { flushSync } from "react-dom";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import type { MouseEvent } from "react";

export function isPlainLeftClick(event: MouseEvent) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

export function navigateWithViewTransition(
  router: AppRouterInstance,
  href: string,
  mode: "enter" | "return",
  beforeNavigate?: () => void,
  afterNavigate?: () => void
) {
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const run = () => {
    beforeNavigate?.();
    flushSync(() => router.push(href));
    afterNavigate?.();
    if (mode === "enter") window.scrollTo(0, 0);
  };

  if (typeof document !== "undefined" && document.startViewTransition && !reduced) {
    document.documentElement.dataset.navigation = mode;
    const transition = document.startViewTransition(run);
    void transition.finished.finally(() => {
      delete document.documentElement.dataset.navigation;
    });
    return;
  }
  run();
}
