import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders confirmation content without modal dialog semantics", () => {
    render(
      <ConfirmDialog
        open
        title="Confirmar exclusao"
        message="Tem certeza?"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(screen.getByText("Confirmar exclusao")).toBeInTheDocument();
    expect(screen.getByText("Tem certeza?")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("calls handlers when action buttons are clicked", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <ConfirmDialog
        open
        title="Confirmar exclusao"
        onConfirm={onConfirm}
        onCancel={onCancel}
        confirmLabel="Confirmar"
        cancelLabel="Cancelar"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /confirmar/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
