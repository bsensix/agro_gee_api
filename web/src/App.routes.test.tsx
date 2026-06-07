import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

function renderWithRouter(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>,
  );
}

it("renders users module route", async () => {
  renderWithRouter("/app/users");
  expect(await screen.findByRole("heading", { name: /usuarios/i })).toBeInTheDocument();
});

it("renders farms module route", async () => {
  renderWithRouter("/app/farms");
  expect(await screen.findByRole("heading", { name: /fazendas/i })).toBeInTheDocument();
});

it("renders fields module route", async () => {
  renderWithRouter("/app/fields");
  expect(await screen.findByRole("heading", { name: /geometrias/i })).toBeInTheDocument();
});

it("redirects root route to users module", async () => {
  renderWithRouter("/");
  expect(await screen.findByRole("heading", { name: /usuarios/i })).toBeInTheDocument();
});

it("falls back unmatched routes to users module", async () => {
  renderWithRouter("/nao-existe");
  expect(await screen.findByRole("heading", { name: /usuarios/i })).toBeInTheDocument();
});
