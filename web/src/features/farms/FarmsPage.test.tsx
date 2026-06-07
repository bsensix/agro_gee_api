import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/http";
import { FarmsPage } from "./FarmsPage";
import * as api from "../../services/api";
import type { Farm } from "../../types/domain";

vi.mock("../../services/api", () => ({
  listFarms: vi.fn(),
  createFarm: vi.fn(),
  updateFarm: vi.fn(),
  deleteFarm: vi.fn(),
}));

const mockedApi = vi.mocked(api);

function makeFarm(overrides: Partial<Farm> = {}): Farm {
  return {
    farm_id: 1,
    user_id: 10,
    name: "Fazenda Aurora",
    geometry: {
      type: "Polygon",
      coordinates: [[[0, 0]]],
    },
    area_ha: "22.4",
    ...overrides,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });

  return { promise, resolve };
}

describe("FarmsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("sends acting user id when listing farms", async () => {
    mockedApi.listFarms.mockResolvedValueOnce([makeFarm()]);

    render(<FarmsPage />);

    expect(await screen.findByRole("cell", { name: "Fazenda Aurora" })).toBeInTheDocument();
    expect(mockedApi.listFarms).toHaveBeenCalledWith(10);
  });

  it("updates list using selected acting user id", async () => {
    mockedApi.listFarms.mockResolvedValueOnce([]).mockResolvedValueOnce([makeFarm({ user_id: 12 })]);

    render(<FarmsPage />);

    await screen.findByRole("heading", { name: /fazendas/i });
    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(1, 10);

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "12" } });

    await waitFor(() => {
      expect(mockedApi.listFarms).toHaveBeenNthCalledWith(2, 12);
    });
  });

  it("shows forbidden guidance on 403 responses", async () => {
    mockedApi.listFarms.mockRejectedValueOnce(new ApiError(403, "Acesso negado."));

    render(<FarmsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/acesso negado para este x-user-id/i);
  });

  it("keeps only latest acting-user list response after rapid switches", async () => {
    const user10Farms = [makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda 10" })];
    const user11Farms = [makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda 11" })];
    const user12Farms = [makeFarm({ farm_id: 12, user_id: 12, name: "Fazenda 12" })];
    const user11Deferred = createDeferred<Farm[]>();
    const user12Deferred = createDeferred<Farm[]>();

    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 10) {
        return Promise.resolve(user10Farms);
      }

      if (userId === 11) {
        return user11Deferred.promise;
      }

      if (userId === 12) {
        return user12Deferred.promise;
      }

      return Promise.resolve([]);
    });

    render(<FarmsPage />);

    expect(await screen.findByRole("cell", { name: "Fazenda 10" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });
    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "12" } });

    await act(async () => {
      user12Deferred.resolve(user12Farms);
    });

    expect(await screen.findByRole("cell", { name: "Fazenda 12" })).toBeInTheDocument();

    await act(async () => {
      user11Deferred.resolve(user11Farms);
    });

    await waitFor(() => expect(screen.getByRole("cell", { name: "Fazenda 12" })).toBeInTheDocument());
    expect(screen.queryByRole("cell", { name: "Fazenda 11" })).not.toBeInTheDocument();

    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(1, 10);
    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(2, 11);
    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(3, 12);
  });

  it("creates a farm and refreshes the list", async () => {
    const initialFarm = makeFarm();
    const createdFarm = makeFarm({ farm_id: 2, name: "Fazenda Horizonte" });

    mockedApi.listFarms.mockResolvedValueOnce([initialFarm]).mockResolvedValueOnce([initialFarm, createdFarm]);
    mockedApi.createFarm.mockResolvedValueOnce(createdFarm);

    render(<FarmsPage />);

    await screen.findByRole("cell", { name: "Fazenda Aurora" });

    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Fazenda Horizonte" } });
    fireEvent.change(screen.getByLabelText(/geometria/i), {
      target: { value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}' },
    });

    fireEvent.click(screen.getByRole("button", { name: /adicionar fazenda/i }));

    await waitFor(() => {
      expect(mockedApi.createFarm).toHaveBeenCalledWith(
        {
          user_id: 10,
          name: "Fazenda Horizonte",
          geometry: {
            type: "Polygon",
            coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]],
          },
        },
        10,
      );
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Fazenda Horizonte" })).toBeInTheDocument();
  });

  it("does not refresh stale acting user after create resolves", async () => {
    const createRequest = createDeferred<Farm>();
    const user10Farms = [makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda 10" })];
    const user11Farms = [makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda 11" })];

    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 10) {
        return Promise.resolve(user10Farms);
      }

      if (userId === 11) {
        return Promise.resolve(user11Farms);
      }

      return Promise.resolve([]);
    });
    mockedApi.createFarm.mockReturnValueOnce(createRequest.promise);

    render(<FarmsPage />);

    expect(await screen.findByRole("cell", { name: "Fazenda 10" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Nova fazenda" } });
    fireEvent.change(screen.getByLabelText(/geometria/i), {
      target: { value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}' },
    });
    fireEvent.click(screen.getByRole("button", { name: /adicionar fazenda/i }));

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Fazenda 11" })).toBeInTheDocument();

    await act(async () => {
      createRequest.resolve(makeFarm({ farm_id: 12, name: "Nova fazenda" }));
    });

    await waitFor(() => {
      expect(mockedApi.createFarm).toHaveBeenCalledTimes(1);
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(2);
    });

    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(1, 10);
    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(2, 11);
    expect(screen.getByRole("cell", { name: "Fazenda 11" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Fazenda 10" })).not.toBeInTheDocument();
  });

  it("updates a farm and refreshes the list", async () => {
    const initialFarm = makeFarm();
    const updatedFarm = makeFarm({ name: "Fazenda Aurora Norte" });

    mockedApi.listFarms.mockResolvedValueOnce([initialFarm]).mockResolvedValueOnce([updatedFarm]);
    mockedApi.updateFarm.mockResolvedValueOnce(updatedFarm);

    render(<FarmsPage />);

    await screen.findByRole("cell", { name: "Fazenda Aurora" });

    fireEvent.click(screen.getByRole("button", { name: /editar fazenda aurora/i }));
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Fazenda Aurora Norte" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar alteracoes/i }));

    await waitFor(() => {
      expect(mockedApi.updateFarm).toHaveBeenCalledWith(
        1,
        {
          user_id: 10,
          name: "Fazenda Aurora Norte",
          geometry: {
            type: "Polygon",
            coordinates: [[[0, 0]]],
          },
        },
        10,
      );
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Fazenda Aurora Norte" })).toBeInTheDocument();
  });

  it("deletes a farm after confirmation and refreshes list", async () => {
    const initialFarm = makeFarm();

    mockedApi.listFarms.mockResolvedValueOnce([initialFarm]).mockResolvedValueOnce([]);
    mockedApi.deleteFarm.mockResolvedValueOnce(undefined);

    render(<FarmsPage />);

    await screen.findByRole("cell", { name: "Fazenda Aurora" });

    fireEvent.click(screen.getByRole("button", { name: /excluir fazenda aurora/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de fazenda aurora/i }));

    await waitFor(() => {
      expect(mockedApi.deleteFarm).toHaveBeenCalledWith(1, 10);
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(2);
    });

    expect(screen.queryByRole("cell", { name: "Fazenda Aurora" })).not.toBeInTheDocument();
  });

  it("does not refresh stale acting user after delete resolves", async () => {
    const deleteRequest = createDeferred<void>();
    const user10Farms = [makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda 10" })];
    const user11Farms = [makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda 11" })];

    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 10) {
        return Promise.resolve(user10Farms);
      }

      if (userId === 11) {
        return Promise.resolve(user11Farms);
      }

      return Promise.resolve([]);
    });
    mockedApi.deleteFarm.mockReturnValueOnce(deleteRequest.promise);

    render(<FarmsPage />);

    expect(await screen.findByRole("cell", { name: "Fazenda 10" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /excluir fazenda 10/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de fazenda 10/i }));

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Fazenda 11" })).toBeInTheDocument();

    await act(async () => {
      deleteRequest.resolve();
    });

    await waitFor(() => {
      expect(mockedApi.deleteFarm).toHaveBeenCalledTimes(1);
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(2);
    });

    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(1, 10);
    expect(mockedApi.listFarms).toHaveBeenNthCalledWith(2, 11);
    expect(screen.getByRole("cell", { name: "Fazenda 11" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Fazenda 10" })).not.toBeInTheDocument();
  });

  it("validates required farm fields before submit", async () => {
    mockedApi.listFarms.mockResolvedValueOnce([]);

    render(<FarmsPage />);

    await screen.findByRole("heading", { name: /fazendas/i });

    fireEvent.change(screen.getByLabelText(/usuario da fazenda/i), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /adicionar fazenda/i }));

    expect(await screen.findByText(/usuario, nome e geometria sao obrigatorios/i)).toBeInTheDocument();
    expect(mockedApi.createFarm).not.toHaveBeenCalled();
    expect(mockedApi.updateFarm).not.toHaveBeenCalled();
  });
});
