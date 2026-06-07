import type { GeoJsonGeometry } from "../../types/domain";

function hasMinimumArrayNesting(value: unknown, depth: number): boolean {
  let current = value;

  for (let level = 0; level < depth; level += 1) {
    if (!Array.isArray(current) || current.length === 0) {
      return false;
    }

    current = current[0];
  }

  return Array.isArray(current);
}

export function parseGeometryInput(raw: string): GeoJsonGeometry {
  let parsed: unknown;

  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("GeoJSON invalido");
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("GeoJSON invalido");
  }

  const geometry = parsed as { type?: unknown; coordinates?: unknown };

  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    throw new Error("GeoJSON geometry deve ser Polygon ou MultiPolygon");
  }

  if (geometry.coordinates === undefined) {
    throw new Error("GeoJSON geometry precisa de coordinates");
  }

  if (geometry.type === "Polygon" && !hasMinimumArrayNesting(geometry.coordinates, 2)) {
    throw new Error("GeoJSON geometry invalida para Polygon");
  }

  if (geometry.type === "MultiPolygon" && !hasMinimumArrayNesting(geometry.coordinates, 3)) {
    throw new Error("GeoJSON geometry invalida para MultiPolygon");
  }

  return {
    type: geometry.type,
    coordinates: geometry.coordinates,
  };
}
