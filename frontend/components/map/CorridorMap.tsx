"use client";

import { useEffect, useMemo } from "react";
import L from "leaflet";
import {
  AttributionControl,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { riskLabel, statusLabel } from "@/lib/labels";
import {
  corridorBounds,
  placeIndex,
  routeSegments,
  shipmentMarkerColor,
  type MapPlace,
  type MapShipment,
} from "@/lib/map/geo";
import styles from "./map.module.css";

type Props = {
  places: MapPlace[];
  shipments: MapShipment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  overview: boolean;
  corridor?: {
    nodes: Array<{ name: string; lat: number; lon: number; kind: string }>;
    segments: Array<{ from: string; to: string; mode: string }>;
  };
};

function FitCorridor({ places, corridor, overview }: { places: MapPlace[]; corridor?: Props["corridor"]; overview: boolean }) {
  const map = useMap();
  useEffect(() => {
    const bounds = overview && corridor?.nodes.length
      ? L.latLngBounds(corridor.nodes.map((node) => [node.lat, node.lon] as [number, number]))
      : L.latLngBounds(corridorBounds(places));
    map.flyToBounds(bounds, { padding: [35, 35], maxZoom: overview ? 5 : 7, duration: 0.65 });
  }, [map, places, corridor, overview]);
  return null;
}

const ATTRIBUTION_PREFIX =
  '<span class="sct-map-brand" aria-hidden="true"></span> LandWay · <a href="https://leafletjs.com" title="Leaflet">Leaflet</a>';

function MapAttributionBranding() {
  const map = useMap();
  useEffect(() => {
    map.attributionControl.setPrefix(ATTRIBUTION_PREFIX);
  }, [map]);
  return null;
}

function FocusSelection({ shipment, places, overview }: { shipment: MapShipment | null; places: MapPlace[]; overview: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!shipment || overview) return;
    const points = routeSegments(shipment.stages, placeIndex(places)).flatMap((segment) => segment.points);
    if (points.length > 1) {
      map.flyToBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 7, duration: 0.6 });
    } else {
      map.flyTo([shipment.position.lat, shipment.position.lon], 6, { duration: 0.6 });
    }
  }, [map, places, shipment?.id, overview]);
  return null;
}

function portIcon() {
  return L.divIcon({
    className: "",
    html: '<div class="port-marker"><div class="port-marker-inner"></div></div>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function cityIcon() {
  return L.divIcon({
    className: "",
    html: '<div class="city-marker"></div>',
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
}

function cargoIcon(color: string) {
  return L.divIcon({
    className: "",
    html: `<div class="cargo-marker" style="background:${color}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

const TRANSPORT_LINE: Record<string, { color: string; dash?: string }> = {
  sea: { color: "#2e6bae", dash: "10 8" },
  rail: { color: "#4800ff" },
  road: { color: "#5d5768", dash: "4 6" },
};

export function CorridorMap({ places, shipments, selectedId, onSelect, corridor, overview }: Props) {
  const index = useMemo(() => placeIndex(places), [places]);
  const selected = shipments.find((s) => s.id === selectedId) ?? null;
  const center = places[0] ? ([places[0].lat, places[0].lon] as [number, number]) : ([46.5, 48] as [number, number]);
  const segments = selected ? routeSegments(selected.stages, index) : [];
  const corridorNodes = new Map(corridor?.nodes.map((node) => [node.name, node]) ?? []);

  return (
    <div className={styles.mapHost}>
      <MapContainer
        center={center}
        zoom={6}
        scrollWheelZoom
        attributionControl={false}
        style={{ height: "100%", width: "100%" }}
      >
        <AttributionControl position="bottomright" prefix={ATTRIBUTION_PREFIX} />
        <MapAttributionBranding />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitCorridor places={places} corridor={corridor} overview={overview} />
        <FocusSelection shipment={selected} places={places} overview={overview} />

        {overview && corridor?.segments.map((segment) => {
          const from = corridorNodes.get(segment.from);
          const to = corridorNodes.get(segment.to);
          if (!from || !to) return null;
          return <Polyline key={`${segment.from}-${segment.to}`} positions={[[from.lat, from.lon], [to.lat, to.lon]]} pathOptions={{ color: segment.mode === "sea" ? "#286b9e" : "#76658d", weight: 3, opacity: 0.8, dashArray: "7 8", lineCap: "round" }} />;
        })}
        {overview && corridor?.nodes.filter((node) => !index.has(node.name)).map((node) => (
          <Marker key={node.name} position={[node.lat, node.lon]} icon={node.kind === "port" ? portIcon() : cityIcon()} title={node.name} alt={node.name}>
            <Tooltip permanent direction="top" offset={[0, -8]} className="place-label">{node.name}</Tooltip>
            <Popup><strong>{node.name}</strong><br />Узел обзорной схемы коридора</Popup>
          </Marker>
        ))}

        {places.map((place) => (
          <Marker
            key={place.name}
            position={[place.lat, place.lon]}
            icon={place.kind === "port" ? portIcon() : cityIcon()}
            zIndexOffset={place.kind === "port" ? 200 : 100}
            title={`${place.kind === "port" ? "Порт" : "Узел"} ${place.name}`}
            alt={place.name}
          >
            <Tooltip permanent direction="top" offset={[0, -8]} className="place-label">
              {place.name}
            </Tooltip>
            <Popup>
              <strong>{place.name}</strong>
              <br />
              {place.kind === "port" ? "Порт" : "Узел"}
              {place.kind === "port" && Number.isFinite(place.workload) && (
                <>
                  <br />
                  Загрузка: {Math.round(place.workload!)}% · демоданные
                </>
              )}
              {place.waitingShipments != null && (
                <>
                  <br />
                  Ожидает: {place.waitingShipments}
                </>
              )}
              {place.weather && (
                <>
                  <br />
                  Погода: {place.weather}
                </>
              )}
            </Popup>
          </Marker>
        ))}

        {segments.map((seg, i) => {
          const style = TRANSPORT_LINE[seg.transport] ?? TRANSPORT_LINE.road;
          const faded = seg.status === "completed";
          return (
            <Polyline
              key={`${selected?.id}-seg-${i}`}
              positions={seg.points}
              pathOptions={{
                color: style.color,
                weight: faded ? 3 : 4,
                opacity: faded ? 0.45 : 0.85,
                dashArray: style.dash,
                lineCap: "round",
              }}
            />
          );
        })}

        {shipments.map((s) => {
          const color = shipmentMarkerColor(s.status, s.riskLevel, s.id === selectedId);
          return (
            <Marker
              key={s.id}
              position={[s.position.lat, s.position.lon]}
              icon={cargoIcon(color)}
              zIndexOffset={s.id === selectedId ? 500 : 300}
              title={`Груз ${s.id}: ${s.position.name} (расчётное положение)`}
              alt={`Груз ${s.id}`}
              eventHandlers={{
                click: () => onSelect(s.id),
              }}
            >
              <Popup>
                <strong>{s.id}</strong> — {s.name}
                <br />
                {statusLabel[s.status] ?? s.status}
                <br />
                Риск: {riskLabel[s.riskLevel] ?? s.riskLevel}
                <br />
                {s.position.name}
                <br />
                Положение расчётное, не GPS
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
