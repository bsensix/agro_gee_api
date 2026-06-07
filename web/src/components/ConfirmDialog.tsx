import { ReactNode } from "react";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div
      style={{
        marginTop: "0.75rem",
        padding: "0.75rem",
        border: "1px solid #c8d0db",
        borderRadius: "8px",
        background: "#f8fafc",
      }}
    >
      <p style={{ margin: 0, fontWeight: 600 }}>{title}</p>
      {message ? <p>{message}</p> : null}
      <button type="button" onClick={onConfirm} disabled={confirmDisabled}>
        {confirmLabel}
      </button>
      <button type="button" onClick={onCancel} style={{ marginLeft: "0.5rem" }}>
        {cancelLabel}
      </button>
    </div>
  );
}
