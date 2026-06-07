import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createFarm,
  createField,
  deleteFarm,
  listUsers,
  getField,
  listFarms,
} from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api service", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists users from /users", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        {
          user_id: 1,
          parent_user_id: null,
          name: "Alice",
          email: "alice@example.com",
          role: "admin",
          created_at: "2026-06-06T12:00:00Z",
        },
      ]),
    );

    const users = await listUsers();

    expect(fetchMock).toHaveBeenCalledWith(
      "/users",
      expect.objectContaining({ method: "GET" }),
    );
    expect(users).toHaveLength(1);
    expect(users[0].name).toBe("Alice");
  });

  it("maps 400 to backend detail and status", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "Invalid geometry payload" }, 400),
    );

    await expect(
      createFarm(
        {
          user_id: 11,
          name: "Farm A",
          geometry: { type: "Polygon", coordinates: [] },
        },
        11,
      ),
    ).rejects.toMatchObject({
      status: 400,
      message: "Invalid geometry payload",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/farms",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-User-Id": "11" }),
      }),
    );
  });

  it("maps 404 to not found error", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "Field not found" }, 404));

    await expect(getField(99, 12)).rejects.toMatchObject({
      status: 404,
      message: "Field not found",
    });
  });

  it("maps 503 to unavailable message", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "db unavailable" }, 503));

    await expect(listFarms(12)).rejects.toMatchObject({
      status: 503,
      message: "Servico indisponivel. Tente novamente em instantes.",
    });
  });

  it("maps fetch transport failures to ApiError shape", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(listUsers()).rejects.toMatchObject({
      status: 0,
      message: "Falha de conexao. Verifique sua internet e tente novamente.",
    });
  });

  it("rejects successful responses with invalid content type", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("ok", {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      }),
    );

    await expect(listUsers()).rejects.toMatchObject({
      status: 502,
      message: "Resposta de sucesso invalida do servidor.",
    });
  });

  it("returns undefined for successful 204 delete", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(deleteFarm(7, 44)).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/farms/7",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "X-User-Id": "44" }),
      }),
    );
  });

  it("sends X-User-Id header for fields endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        field_id: 3,
        farm_id: 7,
        name: "Field A",
        geometry: { type: "Polygon", coordinates: [] },
        area_ha: "10.2",
      }, 201),
    );

    await createField(
      {
        farm_id: 7,
        name: "Field A",
        geometry: { type: "Polygon", coordinates: [] },
      },
      44,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/fields",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-User-Id": "44" }),
      }),
    );
  });
});
