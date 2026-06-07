import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Toast } from "../../components/Toast";
import { ApiError } from "../../lib/http";
import { createField, deleteField, listFarms, listFields, updateField } from "../../services/api";
import type { Farm, Field, FieldPayload } from "../../types/domain";
import { parseGeometryInput } from "./geojson";

type FieldFormState = {
  farmId: string;
  name: string;
  geometry: string;
};

type BannerState = {
  message: string;
  retryable: boolean;
};

type ToastState = {
  tone: "success" | "error" | "info";
  message: string;
};

const DEFAULT_ACTING_USER_ID = 10;

const EMPTY_FORM: FieldFormState = {
  farmId: "",
  name: "",
  geometry: "",
};

export function FieldsPage() {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [actingUserId, setActingUserId] = useState<number>(DEFAULT_ACTING_USER_ID);
  const [form, setForm] = useState<FieldFormState>(EMPTY_FORM);
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [confirmDeleteFieldId, setConfirmDeleteFieldId] = useState<number | null>(null);
  const [isFieldsLoading, setIsFieldsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const latestFarmsRequestIdRef = useRef(0);
  const latestFieldsRequestIdRef = useRef(0);
  const latestGeometryFileReadIdRef = useRef(0);
  const actingUserIdRef = useRef(actingUserId);
  const editingFieldIdRef = useRef<number | null>(editingFieldId);

  useEffect(() => {
    actingUserIdRef.current = actingUserId;
  }, [actingUserId]);

  useEffect(() => {
    editingFieldIdRef.current = editingFieldId;
  }, [editingFieldId]);

  function mapListBanner(unknownError: unknown): BannerState {
    if (unknownError instanceof ApiError) {
      if (unknownError.status === 404) {
        return {
          message: "Nenhum campo foi encontrado para este usuario",
          retryable: true,
        };
      }

      if (unknownError.status === 403) {
        return {
          message: "Acesso negado para este X-User-Id. Ajuste o usuario atuante e tente novamente.",
          retryable: false,
        };
      }

      if (unknownError.status === 503) {
        return {
          message: "Backend indisponivel no momento. Tente novamente em instantes.",
          retryable: false,
        };
      }

      if (unknownError.status === 400) {
        return {
          message: unknownError.message || "Requisicao invalida para carregar campos",
          retryable: false,
        };
      }
    }

    return {
      message: "Nao foi possivel carregar campos",
      retryable: true,
    };
  }

  function mapMutationError(unknownError: unknown): string {
    if (unknownError instanceof ApiError) {
      if (unknownError.status === 400) {
        return unknownError.message || "Dados invalidos para salvar campo";
      }

      if (unknownError.status === 404) {
        return "Campo ou fazenda nao encontrado para este usuario";
      }

      if (unknownError.status === 403) {
        return "Acesso negado para este X-User-Id";
      }
    }

    return "Nao foi possivel salvar campo";
  }

  function mapDeleteError(unknownError: unknown): string {
    if (unknownError instanceof ApiError) {
      if (unknownError.status === 400) {
        return unknownError.message || "Requisicao invalida para excluir campo";
      }

      if (unknownError.status === 404) {
        return "Campo nao encontrado para este usuario";
      }

      if (unknownError.status === 403) {
        return "Acesso negado para este X-User-Id";
      }
    }

    return "Nao foi possivel excluir campo";
  }

  async function invalidateFieldsQuery(userId: number) {
    const requestId = latestFieldsRequestIdRef.current + 1;
    latestFieldsRequestIdRef.current = requestId;
    setIsFieldsLoading(true);

    try {
      const data = await listFields(userId);

      if (latestFieldsRequestIdRef.current !== requestId) {
        return;
      }

      setFields(data);
      setBanner(null);
    } catch (unknownError) {
      if (latestFieldsRequestIdRef.current !== requestId) {
        return;
      }

      setFields([]);
      setBanner(mapListBanner(unknownError));
    } finally {
      if (latestFieldsRequestIdRef.current !== requestId) {
        return;
      }

      setIsFieldsLoading(false);
    }
  }

  async function invalidateFarmsQuery(userId: number) {
    const requestId = latestFarmsRequestIdRef.current + 1;
    latestFarmsRequestIdRef.current = requestId;

    try {
      const data = await listFarms(userId);

      if (latestFarmsRequestIdRef.current !== requestId) {
        return;
      }

      setFarms(data);
      setForm((previous) => {
        const hasCurrentSelection = data.some((farm) => String(farm.farm_id) === previous.farmId);
        if (hasCurrentSelection) {
          return previous;
        }

        return {
          ...previous,
          farmId: data.length > 0 ? String(data[0].farm_id) : "",
        };
      });
    } catch {
      if (latestFarmsRequestIdRef.current !== requestId) {
        return;
      }

      setFarms([]);
      setForm((previous) => ({ ...previous, farmId: "" }));
    }
  }

  useEffect(() => {
    void invalidateFieldsQuery(actingUserId);
    void invalidateFarmsQuery(actingUserId);
  }, [actingUserId]);

  function resetForm() {
    setForm({
      ...EMPTY_FORM,
      farmId: farms.length > 0 ? String(farms[0].farm_id) : "",
    });
    setEditingFieldId(null);
  }

  function validateForm() {
    const parsedFarmId = Number(form.farmId);

    if (!Number.isFinite(parsedFarmId) || parsedFarmId <= 0 || !form.name.trim() || !form.geometry.trim()) {
      setToast({ tone: "error", message: "Id da fazenda, nome e geometria sao obrigatorios" });
      return false;
    }

    if (!Number.isInteger(parsedFarmId)) {
      setToast({ tone: "error", message: "Id da fazenda deve ser inteiro positivo" });
      return false;
    }

    try {
      parseGeometryInput(form.geometry);
    } catch (unknownError) {
      const message = unknownError instanceof Error ? unknownError.message : "GeoJSON invalido";
      setToast({ tone: "error", message });
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

    const mutationActingUserId = actingUserId;
    const payload: FieldPayload = {
      farm_id: Number(form.farmId),
      name: form.name.trim(),
      geometry: parseGeometryInput(form.geometry),
    };

    try {
      setIsSaving(true);

      if (editingFieldId === null) {
        await createField(payload, mutationActingUserId);
      } else {
        await updateField(editingFieldId, payload, mutationActingUserId);
      }

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      await invalidateFieldsQuery(mutationActingUserId);

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      resetForm();
      setToast({ tone: "success", message: "Campo salvo com sucesso" });
    } catch (unknownError) {
      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      setToast({ tone: "error", message: mapMutationError(unknownError) });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGeometryFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];

    if (!selectedFile) {
      return;
    }

    const fileReadId = latestGeometryFileReadIdRef.current + 1;
    latestGeometryFileReadIdRef.current = fileReadId;

    try {
      const fileContent = await selectedFile.text();

      if (latestGeometryFileReadIdRef.current !== fileReadId) {
        return;
      }

      parseGeometryInput(fileContent);
      setForm((previous) => ({ ...previous, geometry: fileContent }));
      setToast(null);
    } catch {
      if (latestGeometryFileReadIdRef.current !== fileReadId) {
        return;
      }

      setForm((previous) => ({ ...previous, geometry: "" }));
      setToast({ tone: "error", message: "Arquivo GeoJSON invalido" });
    }
  }

  function resetUserScopedContext() {
    setEditingFieldId(null);
    setConfirmDeleteFieldId(null);
    setBanner(null);
    setToast(null);
    setForm(EMPTY_FORM);
  }

  function startEdit(field: Field) {
    setToast(null);
    setEditingFieldId(field.field_id);
    setForm({
      farmId: String(field.farm_id),
      name: field.name,
      geometry: JSON.stringify(field.geometry),
    });
    setConfirmDeleteFieldId(null);
  }

  async function confirmDelete(fieldId: number) {
    const mutationActingUserId = actingUserId;

    try {
      setIsDeleting(true);
      await deleteField(fieldId, mutationActingUserId);
      setToast({ tone: "success", message: "Campo excluido com sucesso" });
      setConfirmDeleteFieldId(null);

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      await invalidateFieldsQuery(mutationActingUserId);

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      if (editingFieldIdRef.current === fieldId) {
        resetForm();
      }
    } catch (unknownError) {
      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      setToast({ tone: "error", message: mapDeleteError(unknownError) });
    } finally {
      setIsDeleting(false);
    }
  }

  const editing = editingFieldId !== null;
  const selectedFieldToDelete = fields.find((field) => field.field_id === confirmDeleteFieldId) ?? null;

  return (
    <section>
      <h1>Geometrias</h1>

      {banner ? (
        <div role="alert">
          <p>{banner.message}</p>
          {banner.retryable ? (
            <button type="button" onClick={() => void invalidateFieldsQuery(actingUserId)}>
              Tentar novamente
            </button>
          ) : null}
        </div>
      ) : null}

      {isFieldsLoading ? <p role="status">Carregando campos...</p> : null}

      <label htmlFor="acting-user-id">Usuario atuante</label>
      <input
        id="acting-user-id"
        type="number"
        min={1}
        value={actingUserId}
        onChange={(event) => {
          const nextUserId = Number(event.target.value);
          if (Number.isFinite(nextUserId) && Number.isInteger(nextUserId) && nextUserId > 0) {
            if (nextUserId !== actingUserId) {
              resetUserScopedContext();
            }
            setActingUserId(nextUserId);
          }
        }}
      />

      <form onSubmit={(event) => void handleSubmit(event)} aria-label="Formulario de campo">
        <label htmlFor="field-farm-id">Id da fazenda</label>
        <select
          id="field-farm-id"
          value={form.farmId}
          onChange={(event) => setForm((previous) => ({ ...previous, farmId: event.target.value }))}
        >
          <option value="">Selecione uma fazenda</option>
          {farms.map((farm) => (
            <option key={farm.farm_id} value={farm.farm_id}>
              {farm.name} (ID {farm.farm_id})
            </option>
          ))}
        </select>

        <label htmlFor="field-name">Nome</label>
        <input
          id="field-name"
          value={form.name}
          onChange={(event) => setForm((previous) => ({ ...previous, name: event.target.value }))}
        />

        <label htmlFor="field-geometry">GeoJSON</label>
        <textarea
          id="field-geometry"
          value={form.geometry}
          onChange={(event) => setForm((previous) => ({ ...previous, geometry: event.target.value }))}
        />

        <label htmlFor="field-geometry-file">Arquivo GeoJSON</label>
        <input
          id="field-geometry-file"
          type="file"
          accept=".geojson,.json,application/geo+json,application/json"
          onChange={(event) => void handleGeometryFileChange(event)}
        />

        <button type="submit" disabled={isSaving}>
          {editing ? "Salvar alteracoes" : "Adicionar campo"}
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
            <th>Fazenda</th>
            <th>Area</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const isConfirming = confirmDeleteFieldId === field.field_id;

            return (
              <tr key={field.field_id}>
                <td>{field.name}</td>
                <td>{field.farm_id}</td>
                <td>{field.area_ha}</td>
                <td>
                  <button type="button" onClick={() => startEdit(field)} aria-label={`Editar ${field.name}`}>
                    Editar
                  </button>

                  <button
                    type="button"
                    onClick={() => setConfirmDeleteFieldId(field.field_id)}
                    aria-label={`Excluir ${field.name}`}
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
        open={selectedFieldToDelete !== null}
        title="Confirmar exclusao de campo"
        message={
          selectedFieldToDelete
            ? `Tem certeza que deseja excluir ${selectedFieldToDelete.name}? Esta acao nao pode ser desfeita.`
            : undefined
        }
        confirmLabel={selectedFieldToDelete ? `Confirmar exclusao de ${selectedFieldToDelete.name}` : "Confirmar exclusao"}
        confirmDisabled={isDeleting}
        onConfirm={() => {
          if (selectedFieldToDelete) {
            void confirmDelete(selectedFieldToDelete.field_id);
          }
        }}
        onCancel={() => setConfirmDeleteFieldId(null)}
      />
    </section>
  );
}
