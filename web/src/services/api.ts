import { request } from "../lib/http";
import type {
  Farm,
  FarmPayload,
  Field,
  FieldPayload,
  User,
  UserPayload,
} from "../types/domain";

export function listUsers() {
  return request<User[]>("/users");
}

export function getUser(userId: number) {
  return request<User>(`/users/${userId}`);
}

export function createUser(payload: UserPayload) {
  return request<User, UserPayload>("/users", {
    method: "POST",
    body: payload,
  });
}

export function updateUser(userId: number, payload: UserPayload) {
  return request<User, UserPayload>(`/users/${userId}`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteUser(userId: number) {
  return request<void>(`/users/${userId}`, {
    method: "DELETE",
  });
}

export function listFarms(userId: number) {
  return request<Farm[]>("/farms", { userId });
}

export function getFarm(farmId: number, userId: number) {
  return request<Farm>(`/farms/${farmId}`, { userId });
}

export function createFarm(payload: FarmPayload, userId: number) {
  return request<Farm, FarmPayload>("/farms", {
    method: "POST",
    userId,
    body: payload,
  });
}

export function updateFarm(farmId: number, payload: FarmPayload, userId: number) {
  return request<Farm, FarmPayload>(`/farms/${farmId}`, {
    method: "PUT",
    userId,
    body: payload,
  });
}

export function deleteFarm(farmId: number, userId: number) {
  return request<void>(`/farms/${farmId}`, {
    method: "DELETE",
    userId,
  });
}

export function listFields(userId: number) {
  return request<Field[]>("/fields", { userId });
}

export function getField(fieldId: number, userId: number) {
  return request<Field>(`/fields/${fieldId}`, { userId });
}

export function createField(payload: FieldPayload, userId: number) {
  return request<Field, FieldPayload>("/fields", {
    method: "POST",
    userId,
    body: payload,
  });
}

export function updateField(fieldId: number, payload: FieldPayload, userId: number) {
  return request<Field, FieldPayload>(`/fields/${fieldId}`, {
    method: "PUT",
    userId,
    body: payload,
  });
}

export function deleteField(fieldId: number, userId: number) {
  return request<void>(`/fields/${fieldId}`, {
    method: "DELETE",
    userId,
  });
}
