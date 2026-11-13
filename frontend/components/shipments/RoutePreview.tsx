"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { buildRouteGeometry } from "@/lib/shipments/routeCoords";
import { portPoint } from "@/lib/shipments/ports";
import styles from "./shipmentCards.module.css";

const RoutePreviewMap = dynamic(() => import("./RoutePreviewMap").then((m) => m.RoutePreviewMap), {
  ssr: false,
});

type Stage = { location: string; nextLocation: string; transportType?: string };

type Props = {
  origin: string;
  destination: string;
  stages?: Stage[];
  detail?: boolean;
  embedded?: boolean;
  eager?: boolean;
};

function SchematicFallback({ origin, destination, stages, detail, embedded }: Props) {
  const points: Array<{ x: number; y: number; name: string }> = [];
  const segments: string[] = [];
  const resolve = (name: string) => portPoint(name);

  if (stages?.length) {
    for (const stage of stages) {
      const a = resolve(stage.location);
      const b = resolve(stage.nextLocation);
      if (a && b) segments.push(`${a.x},${a.y} ${b.x},${b.y}`);
      for (const name of [stage.location, stage.nextLocation]) {
        const p = resolve(name);
        if (p && !points.some((item) => item.name === name)) points.push({ ...p, name });
      }
    }
  } else {
    const a = resolve(origin);
    const b = resolve(destination);
    if (a && b) {
      segments.push(`${a.x},${a.y} ${b.x},${b.y}`);
      points.push({ ...a, name: origin }, { ...b, name: destination });
    }
  }

  const label = `${origin} → ${destination}`;

  return (
    <div
      className={detail ? styles.mapPanel : embedded ? styles.mapPreviewEmbedded : styles.mapPreview}
      role="img"
      aria-label={`Схема маршрута ${label}`}
    >
      <svg className={styles.mapSvg} viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <rect className={styles.mapBg} width="100" height="100" />
        {segments.map((pts, i) => (
          <polyline key={i} className={styles.mapRoute} points={pts} />
        ))}
        {points.map((p) => (
          <g key={p.name}>
            <circle className={styles.mapPort} cx={p.x} cy={p.y} r={detail ? 3.2 : 2.6} />
          </g>
        ))}
      </svg>
      {!detail && <span className={styles.mapSchemeNote}>Схема</span>}
    </div>
  );
}

export function RoutePreview({ origin, destination, stages, detail, embedded, eager }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(detail === true);
  const { points, lines, names, modes } = useMemo(() => buildRouteGeometry(origin, destination, stages), [origin, destination, stages]);
  const label = `${origin} → ${destination}`;
  const showMap = detail || eager || active;
  const center = points[0] ?? ([46.5, 48] as [number, number]);

  useEffect(() => {
    if (showMap) return;
    const node = hostRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActive(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [showMap]);

  if (!lines.length) {
    return <SchematicFallback origin={origin} destination={destination} stages={stages} detail={detail} embedded={embedded} />;
  }

  const mapClass = detail ? styles.mapPanel : embedded ? styles.mapPreviewEmbedded : styles.mapPreview;

  return (
    <div
      ref={hostRef}
      className={mapClass}
      role="img"
      aria-label={`Карта маршрута ${label}, OpenStreetMap`}
    >
      <div className={styles.mapPlaceholder} aria-hidden="true">
        <SchematicFallback origin={origin} destination={destination} stages={stages} detail={detail} embedded={embedded} />
      </div>
      {showMap && (
        <RoutePreviewMap
          center={center}
          points={points}
          lines={lines}
          names={names}
          modes={modes}
          detail={detail}
        />
      )}
      <span className={styles.mapOsmCredit}>© OSM</span>
    </div>
  );
}
