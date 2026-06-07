import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/http";
import * as api from "../../services/api";
import type { Farm, Field } from "../../types/domain";
import { FieldsPage } from "./FieldsPage";

vi.mock("../../services/api", () => ({
  listFarms: vi.fn(),
  listFields: vi.fn(),
  createField: vi.fn(),
  updateField: vi.fn(),
  deleteField: vi.fn(),
}));

const mockedApi = vi.mocked(api);

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

function makeField(overrides: Partial<Field> = {}): Field {
  return {
    field_id: 1,
    farm_id: 10,
    name: "Talhao Sul",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [0, 0],
          [0, 1],
          [1, 1],
          [0, 0],
        ],
      ],
    },
    area_ha: "8.2",
    ...overrides,
  };
}

function makeFarm(overrides: Partial<Farm> = {}): Farm {
  return {
    farm_id: 10,
    user_id: 10,
    name: "Fazenda Aurora",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [0, 0],
          [0, 1],
          [1, 1],
          [0, 0],
        ],
      ],
    },
    area_ha: "22.4",
    ...overrides,
  };
}

describe("FieldsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedApi.listFarms.mockResolvedValue([makeFarm()]);
  });

  it("rejects invalid JSON before API call", async () => {
    mockedApi.listFields.mockResolvedValueOnce([]);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Norte" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), { target: { value: "{" } });

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    expect(await screen.findByText(/geojson invalido/i)).toBeInTheDocument();
    expect(mockedApi.createField).not.toHaveBeenCalled();
  });

  it("accepts Polygon geometry object and posts payload", async () => {
    const createdField = makeField({ field_id: 2, name: "Talhao Norte" });

    mockedApi.listFields.mockResolvedValueOnce([]).mockResolvedValueOnce([createdField]);
    mockedApi.createField.mockResolvedValueOnce(createdField);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Norte" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), {
      target: {
        value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}',
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    await waitFor(() => {
      expect(mockedApi.createField).toHaveBeenCalledWith(
        {
          farm_id: 10,
          name: "Talhao Norte",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [0, 0],
                [0, 1],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        10,
      );
      expect(mockedApi.listFields).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Talhao Norte" })).toBeInTheDocument();
  });

  it("loads acting-user farms into selector and submits selected farm id", async () => {
    mockedApi.listFields.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    mockedApi.listFarms.mockResolvedValueOnce([
      makeFarm({ farm_id: 10, name: "Fazenda Aurora" }),
      makeFarm({ farm_id: 11, name: "Fazenda Horizonte" }),
    ]);
    mockedApi.createField.mockResolvedValueOnce(makeField({ field_id: 3, farm_id: 11, name: "Talhao Centro" }));

    render(<FieldsPage />);

    await screen.findByRole("option", { name: "Fazenda Aurora (ID 10)" });
    expect(screen.getByRole("option", { name: "Fazenda Horizonte (ID 11)" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "11" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Centro" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), {
      target: {
        value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}',
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    await waitFor(() => {
      expect(mockedApi.createField).toHaveBeenCalledWith(
        {
          farm_id: 11,
          name: "Talhao Centro",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [0, 0],
                [0, 1],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        10,
      );
    });
  });

  it("lists existing fields and supports edit/delete flows with refresh", async () => {
    const initialField = makeField();
    const updatedField = makeField({ name: "Talhao Sul Atualizado" });

    mockedApi.listFields
      .mockResolvedValueOnce([initialField])
      .mockResolvedValueOnce([updatedField])
      .mockResolvedValueOnce([]);
    mockedApi.updateField.mockResolvedValueOnce(updatedField);
    mockedApi.deleteField.mockResolvedValueOnce(undefined);

    render(<FieldsPage />);

    await screen.findByRole("cell", { name: "Talhao Sul" });

    fireEvent.click(screen.getByRole("button", { name: /editar talhao sul/i }));
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Sul Atualizado" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar alteracoes/i }));

    await waitFor(() => {
      expect(mockedApi.updateField).toHaveBeenCalledWith(
        1,
        {
          farm_id: 10,
          name: "Talhao Sul Atualizado",
          geometry: initialField.geometry,
        },
        10,
      );
      expect(mockedApi.listFields).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Talhao Sul Atualizado" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /excluir talhao sul atualizado/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de talhao sul atualizado/i }));

    await waitFor(() => {
      expect(mockedApi.deleteField).toHaveBeenCalledWith(1, 10);
      expect(mockedApi.listFields).toHaveBeenCalledTimes(3);
    });
  });

  it("shows delete-specific fallback message when delete fails", async () => {
    mockedApi.listFields.mockResolvedValueOnce([makeField()]);
    mockedApi.deleteField.mockRejectedValueOnce(new Error("network"));

    render(<FieldsPage />);

    await screen.findByRole("cell", { name: "Talhao Sul" });

    fireEvent.click(screen.getByRole("button", { name: /excluir talhao sul/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de talhao sul/i }));

    expect(await screen.findByText(/nao foi possivel excluir campo/i)).toBeInTheDocument();
  });

  it("shows friendly message and retry action for 404 on refresh", async () => {
    mockedApi.listFields.mockRejectedValueOnce(new ApiError(404, "Recurso nao encontrado."));

    render(<FieldsPage />);

    expect(await screen.findByText(/nenhum campo foi encontrado para este usuario/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tentar novamente/i })).toBeInTheDocument();
  });

  it("shows retry action on unexpected error", async () => {
    mockedApi.listFields.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce([]);

    render(<FieldsPage />);

    const retryButton = await screen.findByRole("button", { name: /tentar novamente/i });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(mockedApi.listFields).toHaveBeenCalledTimes(2);
    });
  });

  it("does not show stale submit error after acting user changes", async () => {
    const createRequest = createDeferred<Field>();

    mockedApi.listFields
      .mockResolvedValueOnce([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })])
      .mockResolvedValueOnce([makeField({ field_id: 11, name: "Talhao User 11", farm_id: 11 })]);
    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 11) {
        return Promise.resolve([makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda User 11" })]);
      }

      return Promise.resolve([makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda User 10" })]);
    });
    mockedApi.createField.mockReturnValueOnce(createRequest.promise);

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao User 10" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Novo Talhao" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), {
      target: { value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}' },
    });
    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Talhao User 11" })).toBeInTheDocument();

    await act(async () => {
      createRequest.reject(new ApiError(400, "Erro antigo do usuario 10"));
    });

    await waitFor(() => {
      expect(screen.queryByText(/erro antigo do usuario 10/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/nao foi possivel salvar campo/i)).not.toBeInTheDocument();
    });
  });

  it("clears stale rows when active user refresh fails after user switch", async () => {
    mockedApi.listFields
      .mockResolvedValueOnce([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })])
      .mockRejectedValueOnce(new ApiError(404, "Recurso nao encontrado."));

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao User 10" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByText(/nenhum campo foi encontrado para este usuario/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByRole("cell", { name: "Talhao User 10" })).not.toBeInTheDocument();
    });
  });

  it("clears edit and delete context when acting user changes", async () => {
    mockedApi.listFields
      .mockResolvedValueOnce([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })])
      .mockResolvedValueOnce([makeField({ field_id: 11, name: "Talhao User 11", farm_id: 11 })]);
    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 11) {
        return Promise.resolve([makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda User 11" })]);
      }

      return Promise.resolve([makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda User 10" })]);
    });

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao User 10" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /editar talhao user 10/i }));
    expect(screen.getByRole("button", { name: /salvar alteracoes/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancelar edicao/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /excluir talhao user 10/i }));
    expect(screen.getByRole("button", { name: /confirmar exclusao de talhao user 10/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Talhao User 11" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /salvar alteracoes/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /cancelar edicao/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /confirmar exclusao de talhao user 11/i })).not.toBeInTheDocument();
      expect(screen.getByLabelText(/^nome$/i)).toHaveValue("");
      expect(screen.getByLabelText(/^geojson$/i)).toHaveValue("");
    });
  });

  it("validates required fields before submit", async () => {
    mockedApi.listFields.mockResolvedValueOnce([]);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });
    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    expect(await screen.findByText(/id da fazenda, nome e geometria sao obrigatorios/i)).toBeInTheDocument();
    expect(mockedApi.createField).not.toHaveBeenCalled();
    expect(mockedApi.updateField).not.toHaveBeenCalled();
  });

  it("loads geometry from .geojson file input", async () => {
    const createdField = makeField({ field_id: 2, name: "Talhao Leste" });
    const file = new File(["placeholder"], "talhao.geojson", { type: "application/geo+json" });
    const fileText = vi
      .fn()
      .mockResolvedValue('{"type":"Polygon","coordinates":[[[0,0],[0,2],[2,2],[0,0]]]}');

    Object.defineProperty(file, "text", { value: fileText });

    mockedApi.listFields.mockResolvedValueOnce([]).mockResolvedValueOnce([createdField]);
    mockedApi.createField.mockResolvedValueOnce(createdField);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Leste" } });
    fireEvent.change(screen.getByLabelText(/arquivo geojson/i), {
      target: { files: [file] },
    });

    await waitFor(() => {
      expect(fileText).toHaveBeenCalledTimes(1);
      expect(screen.getByLabelText(/^geojson$/i)).toHaveValue(
        '{"type":"Polygon","coordinates":[[[0,0],[0,2],[2,2],[0,0]]]}',
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    await waitFor(() => {
      expect(mockedApi.createField).toHaveBeenCalledWith(
        {
          farm_id: 10,
          name: "Talhao Leste",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [0, 0],
                [0, 2],
                [2, 2],
                [0, 0],
              ],
            ],
          },
        },
        10,
      );
    });
  });

  it("keeps latest geometry when older file read resolves later", async () => {
    const slowerFile = new File(["placeholder"], "talhao-antigo.geojson", { type: "application/geo+json" });
    const latestFile = new File(["placeholder"], "talhao-recente.geojson", { type: "application/geo+json" });
    const slowerFileRead = createDeferred<string>();
    const latestFileRead = createDeferred<string>();

    Object.defineProperty(slowerFile, "text", { value: vi.fn().mockReturnValue(slowerFileRead.promise) });
    Object.defineProperty(latestFile, "text", { value: vi.fn().mockReturnValue(latestFileRead.promise) });

    mockedApi.listFields.mockResolvedValueOnce([]);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    const fileInput = screen.getByLabelText(/arquivo geojson/i);

    fireEvent.change(fileInput, { target: { files: [slowerFile] } });
    fireEvent.change(fileInput, { target: { files: [latestFile] } });

    await act(async () => {
      latestFileRead.resolve('{"type":"Polygon","coordinates":[[[0,0],[0,2],[2,2],[0,0]]]}');
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/^geojson$/i)).toHaveValue(
        '{"type":"Polygon","coordinates":[[[0,0],[0,2],[2,2],[0,0]]]}',
      );
    });

    await act(async () => {
      slowerFileRead.resolve('{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}');
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/^geojson$/i)).toHaveValue(
        '{"type":"Polygon","coordinates":[[[0,0],[0,2],[2,2],[0,0]]]}',
      );
    });
  });

  it("shows validation message for invalid .json upload and avoids API call", async () => {
    const invalidFile = new File(["{"], "talhao.json", { type: "application/json" });
    const fileText = vi.fn().mockResolvedValue("{");

    Object.defineProperty(invalidFile, "text", { value: fileText });
    mockedApi.listFields.mockResolvedValueOnce([]);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/arquivo geojson/i), {
      target: { files: [invalidFile] },
    });

    expect(await screen.findByText(/arquivo geojson invalido/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Oeste" } });
    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    expect(mockedApi.createField).not.toHaveBeenCalled();
  });

  it("clears stale geometry after invalid file upload and blocks submit", async () => {
    const invalidFile = new File(["{"], "talhao.json", { type: "application/json" });
    const invalidFileText = vi.fn().mockResolvedValue("{");

    Object.defineProperty(invalidFile, "text", { value: invalidFileText });
    mockedApi.listFields.mockResolvedValueOnce([]);

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Oeste" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), {
      target: { value: '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[0,0]]]}' },
    });

    fireEvent.change(screen.getByLabelText(/arquivo geojson/i), {
      target: { files: [invalidFile] },
    });

    expect(await screen.findByText(/arquivo geojson invalido/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^geojson$/i)).toHaveValue("");

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    expect(await screen.findByText(/id da fazenda, nome e geometria sao obrigatorios/i)).toBeInTheDocument();
    expect(mockedApi.createField).not.toHaveBeenCalled();
  });

  it("rejects Polygon geometry with invalid coordinate nesting", async () => {
    mockedApi.listFields.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    mockedApi.createField.mockResolvedValueOnce(makeField({ field_id: 2, name: "Talhao Norte" }));

    render(<FieldsPage />);

    await screen.findByRole("heading", { name: /geometrias/i });

    fireEvent.change(screen.getByLabelText(/id da fazenda/i), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/^nome$/i), { target: { value: "Talhao Norte" } });
    fireEvent.change(screen.getByLabelText(/^geojson$/i), {
      target: {
        value: '{"type":"Polygon","coordinates":[0,1]}',
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /adicionar campo/i }));

    expect(await screen.findByText(/geojson geometry invalida para polygon/i)).toBeInTheDocument();
    expect(mockedApi.createField).not.toHaveBeenCalled();
  });

  it("does not show stale delete error after acting user changes", async () => {
    const deleteRequest = createDeferred<void>();

    mockedApi.listFields
      .mockResolvedValueOnce([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })])
      .mockResolvedValueOnce([makeField({ field_id: 11, name: "Talhao User 11", farm_id: 11 })]);
    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 11) {
        return Promise.resolve([makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda User 11" })]);
      }

      return Promise.resolve([makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda User 10" })]);
    });
    mockedApi.deleteField.mockReturnValueOnce(deleteRequest.promise);

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao User 10" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /excluir talhao user 10/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de talhao user 10/i }));

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Talhao User 11" })).toBeInTheDocument();

    await act(async () => {
      deleteRequest.reject(new Error("network"));
    });

    await waitFor(() => {
      expect(screen.queryByText(/nao foi possivel excluir campo/i)).not.toBeInTheDocument();
    });
  });

  it("does not reset current user edit state when stale delete succeeds", async () => {
    const deleteRequest = createDeferred<void>();
    const staleRefreshRequest = createDeferred<Field[]>();
    let user10ListCalls = 0;

    mockedApi.listFields.mockImplementation((userId: number) => {
      if (userId === 11) {
        return Promise.resolve([makeField({ field_id: 10, farm_id: 11, name: "Talhao User 11" })]);
      }

      user10ListCalls += 1;
      if (user10ListCalls === 2) {
        return staleRefreshRequest.promise;
      }

      return Promise.resolve([makeField({ field_id: 10, farm_id: 10, name: "Talhao User 10" })]);
    });
    mockedApi.listFarms.mockImplementation((userId: number) => {
      if (userId === 11) {
        return Promise.resolve([makeFarm({ farm_id: 11, user_id: 11, name: "Fazenda User 11" })]);
      }

      return Promise.resolve([makeFarm({ farm_id: 10, user_id: 10, name: "Fazenda User 10" })]);
    });
    mockedApi.deleteField.mockReturnValueOnce(deleteRequest.promise);

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao User 10" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /editar talhao user 10/i }));
    fireEvent.click(screen.getByRole("button", { name: /excluir talhao user 10/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de talhao user 10/i }));

    await act(async () => {
      deleteRequest.resolve();
    });

    await waitFor(() => {
      expect(mockedApi.listFields).toHaveBeenCalledTimes(2);
    });

    fireEvent.change(screen.getByLabelText(/usuario atuante/i), { target: { value: "11" } });

    expect(await screen.findByRole("cell", { name: "Talhao User 11" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /editar talhao user 11/i }));
    expect(screen.getByLabelText(/^nome$/i)).toHaveValue("Talhao User 11");

    await act(async () => {
      staleRefreshRequest.resolve([]);
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /salvar alteracoes/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /cancelar edicao/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/^nome$/i)).toHaveValue("Talhao User 11");
    });
  });

  it("preserves latest edit target when an earlier delete resolves", async () => {
    const deleteRequest = createDeferred<void>();
    const fieldA = makeField({ field_id: 10, name: "Talhao A" });
    const fieldB = makeField({ field_id: 11, name: "Talhao B", farm_id: 10 });

    mockedApi.listFields.mockResolvedValueOnce([fieldA, fieldB]).mockResolvedValueOnce([fieldB]);
    mockedApi.deleteField.mockReturnValueOnce(deleteRequest.promise);

    render(<FieldsPage />);

    expect(await screen.findByRole("cell", { name: "Talhao A" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Talhao B" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /editar talhao a/i }));
    expect(screen.getByRole("button", { name: /salvar alteracoes/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^nome$/i)).toHaveValue("Talhao A");

    fireEvent.click(screen.getByRole("button", { name: /excluir talhao a/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de talhao a/i }));

    fireEvent.click(screen.getByRole("button", { name: /editar talhao b/i }));
    expect(screen.getByLabelText(/^nome$/i)).toHaveValue("Talhao B");

    await act(async () => {
      deleteRequest.resolve();
    });

    await waitFor(() => {
      expect(mockedApi.deleteField).toHaveBeenCalledWith(10, 10);
      expect(screen.getByRole("button", { name: /salvar alteracoes/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /cancelar edicao/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/^nome$/i)).toHaveValue("Talhao B");
    });
  });

  it("keeps latest acting user list when slower stale requests resolve later", async () => {
    const deferredByUserId = new Map<number, ReturnType<typeof createDeferred<Field[]>>>();

    mockedApi.listFields.mockImplementation((userId: number) => {
      const deferred = createDeferred<Field[]>();
      deferredByUserId.set(userId, deferred);
      return deferred.promise;
    });

    render(<FieldsPage />);

    const actingUserInput = await screen.findByLabelText(/usuario atuante/i);

    fireEvent.change(actingUserInput, { target: { value: "11" } });
    fireEvent.change(actingUserInput, { target: { value: "12" } });

    deferredByUserId.get(12)?.resolve([makeField({ field_id: 12, name: "Talhao User 12", farm_id: 12 })]);
    expect(await screen.findByRole("cell", { name: "Talhao User 12" })).toBeInTheDocument();

    deferredByUserId.get(11)?.resolve([makeField({ field_id: 11, name: "Talhao User 11", farm_id: 11 })]);
    deferredByUserId.get(10)?.resolve([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })]);

    await waitFor(() => {
      expect(screen.queryByRole("cell", { name: "Talhao User 11" })).not.toBeInTheDocument();
      expect(screen.queryByRole("cell", { name: "Talhao User 10" })).not.toBeInTheDocument();
      expect(screen.getByRole("cell", { name: "Talhao User 12" })).toBeInTheDocument();
    });
  });

  it("ignores decimal acting user id input", async () => {
    mockedApi.listFields.mockResolvedValueOnce([makeField({ field_id: 10, name: "Talhao User 10", farm_id: 10 })]);

    render(<FieldsPage />);

    await screen.findByRole("cell", { name: "Talhao User 10" });
    const actingUserInput = screen.getByLabelText(/usuario atuante/i);

    await waitFor(() => {
      expect(mockedApi.listFields).toHaveBeenCalledTimes(1);
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(actingUserInput, { target: { value: "10.5" } });

    await waitFor(() => {
      expect(mockedApi.listFields).toHaveBeenCalledTimes(1);
      expect(mockedApi.listFarms).toHaveBeenCalledTimes(1);
      expect(actingUserInput).toHaveValue(10);
    });
  });
});
