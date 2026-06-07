import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/http";
import { UsersPage } from "./UsersPage";
import * as api from "../../services/api";
import type { User } from "../../types/domain";

vi.mock("../../services/api", () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
}));

const mockedApi = vi.mocked(api);

function makeUser(overrides: Partial<User> = {}): User {
  return {
    user_id: 1,
    parent_user_id: null,
    name: "Ana Silva",
    email: "ana@example.com",
    role: "admin",
    created_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("UsersPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("lists users on load", async () => {
    mockedApi.listUsers.mockResolvedValueOnce([makeUser()]);

    render(<UsersPage />);

    expect(await screen.findByRole("cell", { name: "Ana Silva" })).toBeInTheDocument();
    expect(mockedApi.listUsers).toHaveBeenCalledTimes(1);
  });

  it("shows unavailable banner on 503 responses", async () => {
    mockedApi.listUsers.mockRejectedValueOnce(new ApiError(503, "Servico indisponivel."));

    render(<UsersPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/backend indisponivel/i);
  });

  it("shows users-specific guidance on 403 responses", async () => {
    mockedApi.listUsers.mockRejectedValueOnce(new ApiError(403, "Acesso negado."));

    render(<UsersPage />);

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent(/acesso negado para visualizar usuarios/i);
    expect(banner).not.toHaveTextContent(/x-user-id/i);
  });

  it("creates a user and refreshes the list", async () => {
    const initialUser = makeUser();
    const createdUser = makeUser({
      user_id: 2,
      name: "Bruno Costa",
      email: "bruno@example.com",
      role: "viewer",
    });

    mockedApi.listUsers
      .mockResolvedValueOnce([initialUser])
      .mockResolvedValueOnce([initialUser, createdUser]);
    mockedApi.createUser.mockResolvedValueOnce(createdUser);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "Bruno Costa" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "bruno@example.com" } });
    fireEvent.change(screen.getByLabelText(/perfil/i), { target: { value: "viewer" } });

    fireEvent.click(screen.getByRole("button", { name: /adicionar usuario/i }));

    await waitFor(() => {
      expect(mockedApi.createUser).toHaveBeenCalledWith({
        name: "Bruno Costa",
        email: "bruno@example.com",
        role: "viewer",
        parent_user_id: null,
      });
      expect(mockedApi.listUsers).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Bruno Costa" })).toBeInTheDocument();
  });

  it("submits parent_user_id when creating a user", async () => {
    const initialUser = makeUser();
    const createdUser = makeUser({
      user_id: 2,
      parent_user_id: 1,
      name: "Bruno Costa",
      email: "bruno@example.com",
      role: "viewer",
    });

    mockedApi.listUsers
      .mockResolvedValueOnce([initialUser])
      .mockResolvedValueOnce([initialUser, createdUser]);
    mockedApi.createUser.mockResolvedValueOnce(createdUser);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "Bruno Costa" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "bruno@example.com" } });
    fireEvent.change(screen.getByLabelText(/perfil/i), { target: { value: "viewer" } });
    fireEvent.change(screen.getByLabelText(/usuario pai/i), { target: { value: "1" } });

    fireEvent.click(screen.getByRole("button", { name: /adicionar usuario/i }));

    await waitFor(() => {
      expect(mockedApi.createUser).toHaveBeenCalledWith({
        name: "Bruno Costa",
        email: "bruno@example.com",
        role: "viewer",
        parent_user_id: 1,
      });
    });
  });

  it("updates a user and refreshes the list", async () => {
    const initialUser = makeUser();
    const updatedUser = makeUser({ name: "Ana Souza" });

    mockedApi.listUsers.mockResolvedValueOnce([initialUser]).mockResolvedValueOnce([updatedUser]);
    mockedApi.updateUser.mockResolvedValueOnce(updatedUser);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.click(screen.getByRole("button", { name: /editar ana silva/i }));
    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "Ana Souza" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar alteracoes/i }));

    await waitFor(() => {
      expect(mockedApi.updateUser).toHaveBeenCalledWith(1, {
        name: "Ana Souza",
        email: "ana@example.com",
        role: "admin",
        parent_user_id: null,
      });
      expect(mockedApi.listUsers).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole("cell", { name: "Ana Souza" })).toBeInTheDocument();
  });

  it("loads and submits parent_user_id when editing a user", async () => {
    const initialUser = makeUser({ parent_user_id: 2 });
    const updatedUser = makeUser({ parent_user_id: 3 });

    mockedApi.listUsers.mockResolvedValueOnce([initialUser]).mockResolvedValueOnce([updatedUser]);
    mockedApi.updateUser.mockResolvedValueOnce(updatedUser);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.click(screen.getByRole("button", { name: /editar ana silva/i }));

    const parentInput = screen.getByLabelText(/usuario pai/i) as HTMLInputElement;
    expect(parentInput.value).toBe("2");

    fireEvent.change(parentInput, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar alteracoes/i }));

    await waitFor(() => {
      expect(mockedApi.updateUser).toHaveBeenCalledWith(1, {
        name: "Ana Silva",
        email: "ana@example.com",
        role: "admin",
        parent_user_id: 3,
      });
    });
  });

  it("deletes a user after confirmation and refreshes the list", async () => {
    const initialUser = makeUser();

    mockedApi.listUsers.mockResolvedValueOnce([initialUser]).mockResolvedValueOnce([]);
    mockedApi.deleteUser.mockResolvedValueOnce(undefined);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.click(screen.getByRole("button", { name: /excluir ana silva/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de ana silva/i }));

    await waitFor(() => {
      expect(mockedApi.deleteUser).toHaveBeenCalledWith(1);
      expect(mockedApi.listUsers).toHaveBeenCalledTimes(2);
    });

    expect(screen.queryByRole("cell", { name: "Ana Silva" })).not.toBeInTheDocument();
  });

  it("validates required fields before submit", async () => {
    mockedApi.listUsers.mockResolvedValueOnce([]);

    render(<UsersPage />);

    await screen.findByRole("heading", { name: /usuarios/i });
    fireEvent.click(screen.getByRole("button", { name: /adicionar usuario/i }));

    expect(await screen.findByText(/nome, email e perfil sao obrigatorios/i)).toBeInTheDocument();
    expect(mockedApi.createUser).not.toHaveBeenCalled();
    expect(mockedApi.updateUser).not.toHaveBeenCalled();
  });

  it("blocks submit when email format is invalid", async () => {
    mockedApi.listUsers.mockResolvedValueOnce([]);

    render(<UsersPage />);

    await screen.findByRole("heading", { name: /usuarios/i });
    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "Ana Silva" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "invalid-email" } });
    fireEvent.change(screen.getByLabelText(/perfil/i), { target: { value: "admin" } });

    fireEvent.click(screen.getByRole("button", { name: /adicionar usuario/i }));

    expect(await screen.findByText(/email invalido/i)).toBeInTheDocument();
    expect(mockedApi.createUser).not.toHaveBeenCalled();
    expect(mockedApi.updateUser).not.toHaveBeenCalled();
  });

  it("clears stale list error after retry refresh succeeds", async () => {
    const createdUser = makeUser({
      user_id: 2,
      name: "Bruno Costa",
      email: "bruno@example.com",
      role: "viewer",
    });

    mockedApi.listUsers.mockRejectedValueOnce(new Error("network"));
    mockedApi.createUser.mockResolvedValueOnce(createdUser);
    mockedApi.listUsers.mockResolvedValueOnce([createdUser]);

    render(<UsersPage />);

    expect(await screen.findByText(/nao foi possivel carregar usuarios/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "Bruno Costa" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "bruno@example.com" } });
    fireEvent.change(screen.getByLabelText(/perfil/i), { target: { value: "viewer" } });
    fireEvent.click(screen.getByRole("button", { name: /adicionar usuario/i }));

    expect(await screen.findByRole("cell", { name: "Bruno Costa" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/nao foi possivel carregar usuarios/i)).not.toBeInTheDocument();
    });
  });

  it("clears stale delete error after retry delete succeeds", async () => {
    const initialUser = makeUser();

    mockedApi.listUsers.mockResolvedValueOnce([initialUser]).mockResolvedValueOnce([]);
    mockedApi.deleteUser.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(undefined);

    render(<UsersPage />);

    await screen.findByRole("cell", { name: "Ana Silva" });

    fireEvent.click(screen.getByRole("button", { name: /excluir ana silva/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de ana silva/i }));

    expect(await screen.findByText(/nao foi possivel excluir usuario/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /confirmar exclusao de ana silva/i }));

    await waitFor(() => {
      expect(mockedApi.deleteUser).toHaveBeenCalledTimes(2);
      expect(mockedApi.listUsers).toHaveBeenCalledTimes(2);
    });

    expect(screen.queryByText(/nao foi possivel excluir usuario/i)).not.toBeInTheDocument();
  });
});
