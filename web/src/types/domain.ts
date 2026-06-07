export type GeoJsonGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: unknown;
};

export type User = {
  user_id: number;
  parent_user_id: number | null;
  name: string;
  email: string;
  role: string;
  created_at: string;
};

export type UserPayload = {
  name: string;
  email: string;
  role: string;
  parent_user_id?: number | null;
};

export type Farm = {
  farm_id: number;
  user_id: number;
  name: string;
  geometry: GeoJsonGeometry;
  area_ha: string;
};

export type FarmPayload = {
  user_id: number;
  name: string;
  geometry: GeoJsonGeometry;
};

export type Field = {
  field_id: number;
  farm_id: number;
  name: string;
  geometry: GeoJsonGeometry;
  area_ha: string;
};

export type FieldPayload = {
  farm_id: number;
  name: string;
  geometry: GeoJsonGeometry;
};
