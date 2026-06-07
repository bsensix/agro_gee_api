import { FormEvent, useEffect, useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Toast } from "../../components/Toast";
import { ApiError } from "../../lib/http";
import { createUser, deleteUser, listUsers, updateUser } from "../../services/api";
import type { User, UserPayload } from "../../types/domain";

type UserFormState = {
  name: string;
  email: string;
  role: string;
  parentUserId: string;
};

const EMPTY_FORM: UserFormState = {
  name: "",
  email: "",
  role: "",
  parentUserId: "",
};

type BannerState = {
  message: string;
  retryable: boolean;
};

type ToastState = {
  tone: "success" | "error" | "info";
  message: string;
};

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [confirmDeleteUserId, setConfirmDeleteUserId] = useState<number | null>(null);
  const [isListLoading, setIsListLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  function mapListBanner(unknownError: unknown): BannerState {
    if (unknownError instanceof ApiError) {
      if (unknownError.status === 503) {
        return {
          message: "Backend indisponivel no momento. Tente novamente em instantes.",
          retryable: false,
        };
      }

      if (unknownError.status === 403) {
        return {
          message: "Acesso negado para visualizar usuarios. Verifique suas permissoes e tente novamente.",
          retryable: false,
        };
      }
    }

    return {
      message: "Nao foi possivel carregar usuarios",
      retryable: true,
    };
  }

  async function invalidateUsersQuery() {
    setIsListLoading(true);

    try {
      const data = await listUsers();
      setUsers(data);
      setBanner(null);
    } catch (unknownError) {
      setUsers([]);
      setBanner(mapListBanner(unknownError));
    } finally {
      setIsListLoading(false);
    }
  }

  useEffect(() => {
    void invalidateUsersQuery();
  }, []);

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingUserId(null);
  }

  function validateForm() {
    if (!form.name.trim() || !form.email.trim() || !form.role.trim()) {
      setToast({ tone: "error", message: "Nome, email e perfil sao obrigatorios" });
      return false;
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(form.email.trim())) {
      setToast({ tone: "error", message: "Email invalido" });
      return false;
    }

    return true;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setToast(null);

    if (!validateForm()) {
      return;
    }

    const payload: UserPayload = {
      name: form.name.trim(),
      email: form.email.trim(),
      role: form.role.trim(),
      parent_user_id: form.parentUserId.trim() ? Number(form.parentUserId.trim()) : null,
    };

    try {
      setIsSaving(true);

      if (editingUserId === null) {
        await createUser(payload);
      } else {
        await updateUser(editingUserId, payload);
      }

      await invalidateUsersQuery();
      resetForm();
      setToast({ tone: "success", message: "Usuario salvo com sucesso" });
    } catch {
      setToast({ tone: "error", message: "Nao foi possivel salvar usuario" });
    } finally {
      setIsSaving(false);
    }
  }

  function startEdit(user: User) {
    setToast(null);
    setEditingUserId(user.user_id);
    setForm({
      name: user.name,
      email: user.email,
      role: user.role,
      parentUserId: user.parent_user_id === null ? "" : String(user.parent_user_id),
    });
    setConfirmDeleteUserId(null);
  }

  async function confirmDelete(userId: number) {
    try {
      setIsDeleting(true);
      await deleteUser(userId);
      setToast({ tone: "success", message: "Usuario excluido com sucesso" });
      setConfirmDeleteUserId(null);
      await invalidateUsersQuery();

      if (editingUserId === userId) {
        resetForm();
      }
    } catch {
      setToast({ tone: "error", message: "Nao foi possivel excluir usuario" });
    } finally {
      setIsDeleting(false);
    }
  }

  const editing = editingUserId !== null;
  const selectedUserToDelete = users.find((user) => user.user_id === confirmDeleteUserId) ?? null;

  return (
    <section>
      <h1>Usuarios</h1>

      {banner ? (
        <div role="alert">
          <p>{banner.message}</p>
          {banner.retryable ? (
            <button type="button" onClick={() => void invalidateUsersQuery()}>
              Tentar novamente
            </button>
          ) : null}
        </div>
      ) : null}

      {isListLoading ? <p role="status">Carregando usuarios...</p> : null}

      <form onSubmit={(event) => void handleSubmit(event)} aria-label="Formulario de usuario">
        <label htmlFor="user-name">Nome</label>
        <input
          id="user-name"
          value={form.name}
          onChange={(event) => setForm((previous) => ({ ...previous, name: event.target.value }))}
        />

        <label htmlFor="user-email">Email</label>
        <input
          id="user-email"
          value={form.email}
          onChange={(event) => setForm((previous) => ({ ...previous, email: event.target.value }))}
        />

        <label htmlFor="user-role">Perfil</label>
        <input
          id="user-role"
          value={form.role}
          onChange={(event) => setForm((previous) => ({ ...previous, role: event.target.value }))}
        />

        <label htmlFor="user-parent-id">Usuario pai (ID)</label>
        <input
          id="user-parent-id"
          value={form.parentUserId}
          inputMode="numeric"
          onChange={(event) => setForm((previous) => ({ ...previous, parentUserId: event.target.value }))}
        />

        <button type="submit" disabled={isSaving}>
          {editing ? "Salvar alteracoes" : "Adicionar usuario"}
        </button>
        {editing ? (
          <button type="button" onClick={resetForm} disabled={isSaving}>
            Cancelar edicao
          </button>
        ) : null}
      </form>

      {toast ? <Toast tone={toast.tone} message={toast.message} onClose={() => setToast(null)} /> : null}

      <table>
        <thead>
          <tr>
            <th>Nome</th>
            <th>Email</th>
            <th>Perfil</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const isConfirming = confirmDeleteUserId === user.user_id;

            return (
              <tr key={user.user_id}>
                <td>{user.name}</td>
                <td>{user.email}</td>
                <td>{user.role}</td>
                <td>
                  <button type="button" onClick={() => startEdit(user)} aria-label={`Editar ${user.name}`}>
                    Editar
                  </button>

                  <button
                    type="button"
                    onClick={() => setConfirmDeleteUserId(user.user_id)}
                    aria-label={`Excluir ${user.name}`}
                  >
                    {isConfirming ? "Excluir (confirmando)" : "Excluir"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <ConfirmDialog
        open={selectedUserToDelete !== null}
        title="Confirmar exclusao de usuario"
        message={
          selectedUserToDelete
            ? `Tem certeza que deseja excluir ${selectedUserToDelete.name}? Esta acao nao pode ser desfeita.`
            : undefined
        }
        confirmLabel={selectedUserToDelete ? `Confirmar exclusao de ${selectedUserToDelete.name}` : "Confirmar exclusao"}
        confirmDisabled={isDeleting}
        onConfirm={() => {
          if (selectedUserToDelete) {
            void confirmDelete(selectedUserToDelete.user_id);
          }
        }}
        onCancel={() => setConfirmDeleteUserId(null)}
      />
    </section>
  );
}
