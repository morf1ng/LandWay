"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import styles from "./shipmentCards.module.css";

function MapInvalidate() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

function FitRoute({
  points,
  lines,
  detail,
}: {
  points: [number, number][];
  lines: [number, number][][];
  detail?: boolean;
}) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    const flat = lines.length ? lines.flat() : points;
    map.invalidateSize({ animate: false });
    map.fitBounds(flat, { padding: detail ? [40, 40] : [28, 28], maxZoom: detail ? 9 : 7, animate: false });
  }, [map, points, lines, detail]);
  return null;
}

type Props = {
  center: [number, number];
  points: [number, number][];
  lines: [number, number][][];
  names: string[];
  modes: string[];
  detail?: boolean;
};

const lineStyles: Record<string, { color: string; dashArray?: string }> = {
  sea: { color: "#4800ff", dashArray: "8 7" },
  rail: { color: "#3d3a46" },
  road: { color: "#7150b7", dashArray: "3 6" },
};

export function RoutePreviewMap({ center, points, lines, names, modes, detail }: Props) {
  return (
    <MapContainer
      center={center}
      zoom={detail ? 6 : 5}
      scrollWheelZoom={Boolean(detail)}
      dragging={Boolean(detail)}
      doubleClickZoom={Boolean(detail)}
      touchZoom={Boolean(detail)}
      keyboard={false}
      boxZoom={false}
      trackResize={false}
      zoomControl={Boolean(detail)}
      attributionControl={false}
      className={styles.embeddedMap}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
      <MapInvalidate />
      <FitRoute points={points} lines={lines} detail={detail} />
      {lines.map((line, i) => (
        <Polyline
          key={i}
          positions={line}
          pathOptions={{
            ...(lineStyles[modes[i]] ?? lineStyles.road),
            weight: detail ? 5 : 3,
            opacity: 0.88,
            lineCap: "round",
          }}
        />
      ))}
      {points.map((coord, i) => (
        <CircleMarker
          key={i}
          center={coord}
          radius={detail ? 7 : 5}
          pathOptions={{ color: "#4800ff", weight: 2, fillColor: "#ffffff", fillOpacity: 1 }}
          eventHandlers={
            detail || i === 0 || i === points.length - 1
              ? {
                  add: (event) => {
                    event.target.bindTooltip(names[i] ?? "Узел маршрута", {
                      permanent: true,
                      direction: i === 0 ? "top" : "bottom",
                      offset: [0, i === 0 ? -6 : 6],
                      className: styles.routePointLabel,
                    }).openTooltip();
                  },
                }
              : undefined
          }
        />
      ))}
    </MapContainer>
  );
}
