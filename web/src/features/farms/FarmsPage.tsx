import { FormEvent, useEffect, useRef, useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Toast } from "../../components/Toast";
import { ApiError } from "../../lib/http";
import { createFarm, deleteFarm, listFarms, updateFarm } from "../../services/api";
import type { Farm, FarmPayload, GeoJsonGeometry } from "../../types/domain";

type FarmFormState = {
  farmUserId: string;
  name: string;
  geometry: string;
};

const DEFAULT_ACTING_USER_ID = 10;

const EMPTY_FORM: FarmFormState = {
  farmUserId: String(DEFAULT_ACTING_USER_ID),
  name: "",
  geometry: "",
};

type BannerState = {
  message: string;
  retryable: boolean;
};

type ToastState = {
  tone: "success" | "error" | "info";
  message: string;
};

export function FarmsPage() {
  const [farms, setFarms] = useState<Farm[]>([]);
  const [actingUserId, setActingUserId] = useState<number>(DEFAULT_ACTING_USER_ID);
  const [form, setForm] = useState<FarmFormState>(EMPTY_FORM);
  const [editingFarmId, setEditingFarmId] = useState<number | null>(null);
  const [confirmDeleteFarmId, setConfirmDeleteFarmId] = useState<number | null>(null);
  const [isListLoading, setIsListLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const latestFarmsRequestIdRef = useRef(0);
  const actingUserIdRef = useRef(actingUserId);

  useEffect(() => {
    actingUserIdRef.current = actingUserId;
  }, [actingUserId]);

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
          message: "Acesso negado para este X-User-Id. Ajuste o usuario atuante e tente novamente.",
          retryable: false,
        };
      }
    }

    return {
      message: "Nao foi possivel carregar fazendas",
      retryable: true,
    };
  }

  async function invalidateFarmsQuery(userId: number) {
    const requestId = latestFarmsRequestIdRef.current + 1;
    latestFarmsRequestIdRef.current = requestId;
    setIsListLoading(true);

    try {
      const data = await listFarms(userId);

      if (latestFarmsRequestIdRef.current !== requestId) {
        return;
      }

      setFarms(data);
      setBanner(null);
    } catch (unknownError) {
      if (latestFarmsRequestIdRef.current !== requestId) {
        return;
      }

      setFarms([]);
      setBanner(mapListBanner(unknownError));
    } finally {
      if (latestFarmsRequestIdRef.current !== requestId) {
        return;
      }

      setIsListLoading(false);
    }
  }

  useEffect(() => {
    void invalidateFarmsQuery(actingUserId);
  }, [actingUserId]);

  function resetForm() {
    setForm({ ...EMPTY_FORM, farmUserId: String(actingUserId) });
    setEditingFarmId(null);
  }

  function parseGeometry(rawGeometry: string): GeoJsonGeometry | null {
    try {
      return JSON.parse(rawGeometry) as GeoJsonGeometry;
    } catch {
      return null;
    }
  }

  function validateForm() {
    const parsedFarmUserId = Number(form.farmUserId);

    if (!Number.isFinite(parsedFarmUserId) || parsedFarmUserId <= 0 || !form.name.trim() || !form.geometry.trim()) {
      setToast({ tone: "error", message: "Usuario, nome e geometria sao obrigatorios" });
      return false;
    }

    const parsedGeometry = parseGeometry(form.geometry);

    if (!parsedGeometry || typeof parsedGeometry !== "object" || !("type" in parsedGeometry) || !("coordinates" in parsedGeometry)) {
      setToast({ tone: "error", message: "Geometria deve ser um JSON valido" });
      return false;
    }

    return true;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setToast(null);
    const mutationActingUserId = actingUserId;

    if (!validateForm()) {
      return;
    }

    const payload: FarmPayload = {
      user_id: Number(form.farmUserId),
      name: form.name.trim(),
      geometry: parseGeometry(form.geometry) as GeoJsonGeometry,
    };

    try {
      setIsSaving(true);

      if (editingFarmId === null) {
        await createFarm(payload, mutationActingUserId);
      } else {
        await updateFarm(editingFarmId, payload, mutationActingUserId);
      }

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      await invalidateFarmsQuery(mutationActingUserId);

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      resetForm();
      setToast({ tone: "success", message: "Fazenda salva com sucesso" });
    } catch {
      setToast({ tone: "error", message: "Nao foi possivel salvar fazenda" });
    } finally {
      setIsSaving(false);
    }
  }

  function startEdit(farm: Farm) {
    setToast(null);
    setEditingFarmId(farm.farm_id);
    setForm({
      farmUserId: String(farm.user_id),
      name: farm.name,
      geometry: JSON.stringify(farm.geometry),
    });
    setConfirmDeleteFarmId(null);
  }

  async function confirmDelete(farmId: number) {
    const mutationActingUserId = actingUserId;

    try {
      setIsDeleting(true);
      await deleteFarm(farmId, mutationActingUserId);
      setToast({ tone: "success", message: "Fazenda excluida com sucesso" });
      setConfirmDeleteFarmId(null);

      if (actingUserIdRef.current !== mutationActingUserId) {
        return;
      }

      await invalidateFarmsQuery(mutationActingUserId);

      if (editingFarmId === farmId) {
        resetForm();
      }
    } catch {
      setToast({ tone: "error", message: "Nao foi possivel excluir fazenda" });
    } finally {
      setIsDeleting(false);
    }
  }

  const editing = editingFarmId !== null;
  const selectedFarmToDelete = farms.find((farm) => farm.farm_id === confirmDeleteFarmId) ?? null;

  return (
    <section>
      <h1>Fazendas</h1>

      {banner ? (
        <div role="alert">
          <p>{banner.message}</p>
          {banner.retryable ? (
            <button type="button" onClick={() => void invalidateFarmsQuery(actingUserId)}>
              Tentar novamente
            </button>
          ) : null}
        </div>
      ) : null}

      {isListLoading ? <p role="status">Carregando fazendas...</p> : null}

      <label htmlFor="acting-user-id">Usuario atuante</label>
      <input
        id="acting-user-id"
        type="number"
        min={1}
        value={actingUserId}
        onChange={(event) => {
          const nextUserId = Number(event.target.value);
          if (Number.isFinite(nextUserId) && nextUserId > 0) {
            setActingUserId(nextUserId);
            setForm((previous) => ({ ...previous, farmUserId: String(nextUserId) }));
            setToast(null);
          }
        }}
      />

      <form onSubmit={(event) => void handleSubmit(event)} aria-label="Formulario de fazenda">
        <label htmlFor="farm-user-id">Usuario da fazenda</label>
        <input
          id="farm-user-id"
          type="number"
          min={1}
          value={form.farmUserId}
          onChange={(event) => setForm((previous) => ({ ...previous, farmUserId: event.target.value }))}
        />

        <label htmlFor="farm-name">Nome</label>
        <input
          id="farm-name"
          value={form.name}
          onChange={(event) => setForm((previous) => ({ ...previous, name: event.target.value }))}
        />

        <label htmlFor="farm-geometry">Geometria</label>
        <textarea
          id="farm-geometry"
          value={form.geometry}
          onChange={(event) => setForm((previous) => ({ ...previous, geometry: event.target.value }))}
        />

        <button type="submit" disabled={isSaving}>
          {editing ? "Salvar alteracoes" : "Adicionar fazenda"}
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
            <th>Usuario</th>
            <th>Area</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {farms.map((farm) => {
            const isConfirming = confirmDeleteFarmId === farm.farm_id;

            return (
              <tr key={farm.farm_id}>
                <td>{farm.name}</td>
                <td>{farm.user_id}</td>
                <td>{farm.area_ha}</td>
                <td>
                  <button type="button" onClick={() => startEdit(farm)} aria-label={`Editar ${farm.name}`}>
                    Editar
                  </button>

                  <button
                    type="button"
                    onClick={() => setConfirmDeleteFarmId(farm.farm_id)}
                    aria-label={`Excluir ${farm.name}`}
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
        open={selectedFarmToDelete !== null}
        title="Confirmar exclusao de fazenda"
        message={
          selectedFarmToDelete
            ? `Tem certeza que deseja excluir ${selectedFarmToDelete.name}? Esta acao nao pode ser desfeita.`
            : undefined
        }
        confirmLabel={selectedFarmToDelete ? `Confirmar exclusao de ${selectedFarmToDelete.name}` : "Confirmar exclusao"}
        confirmDisabled={isDeleting}
        onConfirm={() => {
          if (selectedFarmToDelete) {
            void confirmDelete(selectedFarmToDelete.farm_id);
          }
        }}
        onCancel={() => setConfirmDeleteFarmId(null)}
      />
    </section>
  );
}
