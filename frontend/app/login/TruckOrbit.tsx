"use client";

import { useSyncExternalStore } from "react";
import styles from "./login.module.css";

// Замкнутый контур внутри окружности с отступом под ширину грузовика.
const PERIMETER_PATH =
  "M 338.5 26 A 312.5 266.5 0 1 0 338.5 559 A 312.5 266.5 0 1 0 338.5 26 Z";
const motionQuery = "(prefers-reduced-motion: reduce)";

function subscribeToMotion(onChange: () => void) {
  const query = window.matchMedia(motionQuery);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

const prefersReducedMotion = () => window.matchMedia(motionQuery).matches;
const serverMotionPreference = () => false;

export function TruckOrbit() {
  const reducedMotion = useSyncExternalStore(
    subscribeToMotion,
    prefersReducedMotion,
    serverMotionPreference,
  );

  return (
    <div className={styles.purpleRightWrap} aria-hidden="true">
      <svg
        className={styles.routeSvg}
        viewBox="0 0 677 585"
        fill="none"
        focusable="false"
      >
        <path className={styles.dashedPath} d={PERIMETER_PATH} />
        <g
          className={styles.truckRunner}
          transform={reducedMotion ? "translate(26 292.5) rotate(90)" : undefined}
        >
          {!reducedMotion && (
            <animateMotion
              path={PERIMETER_PATH}
              dur="22s"
              begin="-5.5s"
              rotate="auto"
              calcMode="paced"
              repeatCount="indefinite"
            />
          )}

          {/* Шасси и сцепка между тягачом и полуприцепом. */}
          <rect x="3" y="-8" width="24" height="16" rx="3" fill="#262633" />
          <rect x="6" y="-3" width="12" height="6" rx="2" fill="#8c8c9d" />

          {/* Колёса видны по бокам, как при взгляде строго сверху. */}
          <g fill="#15151e">
            <rect x="-39" y="-17" width="9" height="6" rx="2" />
            <rect x="-27" y="-17" width="9" height="6" rx="2" />
            <rect x="-39" y="11" width="9" height="6" rx="2" />
            <rect x="-27" y="11" width="9" height="6" rx="2" />
            <rect x="10" y="-16" width="10" height="6" rx="2" />
            <rect x="10" y="10" width="10" height="6" rx="2" />
            <rect x="33" y="-16" width="9" height="6" rx="2" />
            <rect x="33" y="10" width="9" height="6" rx="2" />
          </g>

          {/* Длинный светлый кузов полуприцепа. */}
          <rect x="-49" y="-13" width="57" height="26" rx="3" fill="#fbfaff" stroke="#d8d4e7" />
          <rect x="-44" y="-9" width="46" height="18" rx="1.5" fill="#f0edf8" />
          <path d="M-36-9v18 M-27-9v18 M-18-9v18 M-9-9v18" stroke="#d9d5e6" strokeWidth="1.2" />
          <path d="M-47-9v18" stroke="#b9b4cd" />
          <path d="M-49-9v4 M-49 5v4" stroke="#ee687a" strokeWidth="2" strokeLinecap="round" />

          {/* Кабина направлена вправо, вдоль касательной к пути. */}
          <rect x="21" y="-18" width="5" height="4" rx="1" fill="#20202b" />
          <rect x="21" y="14" width="5" height="4" rx="1" fill="#20202b" />
          <rect x="17" y="-13" width="29" height="26" rx="5" fill="#fff" stroke="#d8d4e7" />
          <rect x="21" y="-9" width="10" height="18" rx="2" fill="#e7e2f3" />
          <path d="M34-10h5q3 10 0 20h-5q2-10 0-20Z" fill="#313047" />
          <path d="M35-7h2" stroke="#8a89a1" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M43-9v4 M43 5v4" stroke="#b3a2fa" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M46-5v10" stroke="#d0cbdf" strokeWidth="2" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  );
}
