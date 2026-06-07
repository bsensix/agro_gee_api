type ToastTone = "success" | "error" | "info";

type ToastProps = {
  tone?: ToastTone;
  message: string;
  onClose?: () => void;
};

export function Toast({ tone = "info", message, onClose }: ToastProps) {
  const backgroundByTone: Record<ToastTone, string> = {
    success: "#e8f7ec",
    error: "#fdecec",
    info: "#e9f1fb",
  };

  const borderByTone: Record<ToastTone, string> = {
    success: "#2d8a4a",
    error: "#b43b3b",
    info: "#2a63a8",
  };

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        marginTop: "0.75rem",
        padding: "0.6rem 0.75rem",
        borderRadius: "6px",
        border: `1px solid ${borderByTone[tone]}`,
        background: backgroundByTone[tone],
      }}
    >
      {message}
      {onClose ? (
        <button type="button" onClick={onClose} style={{ marginLeft: "0.5rem" }}>
          Fechar
        </button>
      ) : null}
    </div>
  );
}
