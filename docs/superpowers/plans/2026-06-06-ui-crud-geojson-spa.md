# UI CRUD + GeoJSON SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and ship a React SPA served by FastAPI that supports CRUD for users/farms and GeoJSON-based field registration.

**Architecture:** Add a `web/` React+Vite+TypeScript app with route modules (`/app/users`, `/app/farms`, `/app/fields`) and a thin typed API client. Keep backend API contracts unchanged; only extend FastAPI to serve built frontend static assets with SPA fallback.

**Tech Stack:** FastAPI, pytest, React, TypeScript, Vite, React Router, TanStack Query, Vitest, Testing Library

---

## File Structure (planned)

### Backend files

- Modify: `api/main.py` - mount built SPA static files and SPA fallback route.
- Create: `tests/test_web_ui_serving.py` - backend tests for static serving and fallback behavior.

### Frontend app scaffold

- Create: `web/package.json` - frontend scripts and dependencies.
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/styles.css`

### Frontend shared layer

- Create: `web/src/lib/http.ts` - base fetch wrapper and error mapping.
- Create: `web/src/services/api.ts` - typed CRUD functions for users/farms/fields.
- Create: `web/src/types/domain.ts` - shared API DTO types.
- Create: `web/src/components/Layout.tsx` - navigation shell.
- Create: `web/src/components/Toast.tsx` - lightweight status feedback.
- Create: `web/src/components/ConfirmDialog.tsx` - delete confirmation.

### Frontend feature modules

- Create: `web/src/features/users/UsersPage.tsx`
- Create: `web/src/features/farms/FarmsPage.tsx`
- Create: `web/src/features/fields/FieldsPage.tsx`
- Create: `web/src/features/fields/geojson.ts` - parse/shape checks for GeoJSON geometry objects.

### Frontend tests

- Create: `web/vitest.config.ts`
- Create: `web/src/test/setup.ts`
- Create: `web/src/services/api.test.ts`
- Create: `web/src/features/users/UsersPage.test.tsx`
- Create: `web/src/features/farms/FarmsPage.test.tsx`
- Create: `web/src/features/fields/FieldsPage.test.tsx`

### Supporting docs/config

- Modify: `.gitignore` - include `web/node_modules` and `web/dist` ignores if missing.
- Modify: `README.md` - add frontend run/build/test commands and FastAPI serving note.

## Implementation Tasks

### Task 1: FastAPI static hosting contract (TDD first)

**Files:**
- Modify: `api/main.py`
- Create: `tests/test_web_ui_serving.py`

- [ ] **Step 1: Write failing backend tests for static serving behavior**

```python
def test_app_route_returns_200_when_dist_exists(tmp_path, monkeypatch):
    # create fake web/dist/index.html and assert GET /app returns HTML
    ...


def test_app_subroute_falls_back_to_index_html(tmp_path, monkeypatch):
    # assert GET /app/users returns SPA entry
    ...


def test_app_route_returns_404_when_dist_is_missing(monkeypatch):
    # assert GET /app/users returns 404 before frontend build exists
    ...
```

- [ ] **Step 2: Run targeted tests and confirm failure**

Run: `pytest tests/test_web_ui_serving.py -v`
Expected: FAIL because `/app` routes/static mount do not exist yet.

- [ ] **Step 3: Implement minimal FastAPI static mount + fallback**

```python
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="web-assets")


@app.get("/app", include_in_schema=False)
@app.get("/app/{path:path}", include_in_schema=False)
def web_app(path: str = "") -> FileResponse:
    if not web_dist.exists():
        raise HTTPException(status_code=404, detail="Web app not built")
    return FileResponse(web_dist / "index.html")
```

- [ ] **Step 4: Re-run targeted tests**

Run: `pytest tests/test_web_ui_serving.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add api/main.py tests/test_web_ui_serving.py
git commit -m "feat: serve SPA assets and /app fallback from FastAPI"
```

### Task 2: Scaffold React SPA with routing shell

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vite.config.ts`
- Create: `web/vitest.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/styles.css`
- Create: `web/src/components/Layout.tsx`
- Create: `web/src/test/setup.ts`
- Create: `web/src/features/users/UsersPage.tsx` (stub)
- Create: `web/src/features/farms/FarmsPage.tsx` (stub)
- Create: `web/src/features/fields/FieldsPage.tsx` (stub)
- Modify: `.gitignore`

- [ ] **Step 1: Update `.gitignore` before frontend bootstrap artifacts**

Add entries (if missing):

```gitignore
web/node_modules/
web/dist/
```

- [ ] **Step 2: Create frontend manifest/config skeleton (`package.json`, tsconfig, vite config)**

Minimum required first:

```json
{
  "name": "agro-insight-web",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest"
  }
}
```

- [ ] **Step 3: Install frontend dependencies in clean workspace**

Run: `npm --prefix web install`
Expected: PASS, `web/package-lock.json` and `web/node_modules` created.

- [ ] **Step 4: Write failing frontend route smoke tests**

```tsx
it("renders users module route", async () => {
  renderWithRouter("/app/users")
  expect(await screen.findByRole("heading", { name: /usuarios/i })).toBeInTheDocument()
})
```

- [ ] **Step 5: Run test command to capture failure**

Run: `npm --prefix web test -- --run`
Expected: FAIL due to missing app scaffold/routes.

- [ ] **Step 6: Create minimal frontend test harness (Vitest + jsdom) and rerun**

Run: `npm --prefix web test -- --run`
Expected: FAIL with route/component failures (not tooling bootstrap errors).

- [ ] **Step 7: Create Vite React TypeScript scaffold files, route layout, and stub pages**

```tsx
<Routes>
  <Route path="/app" element={<Layout />}>
    <Route path="users" element={<UsersPage />} />
    <Route path="farms" element={<FarmsPage />} />
    <Route path="fields" element={<FieldsPage />} />
  </Route>
</Routes>
```

- [ ] **Step 8: Re-run route smoke tests**

Run: `npm --prefix web test -- --run`
Expected: PASS for route-render smoke tests.

- [ ] **Step 9: Validate production build artifacts**

Run: `npm --prefix web run build`
Expected: PASS, `web/dist/index.html` and hashed assets emitted.

- [ ] **Step 10: Commit Task 2 with path-scoped adds**

```bash
git add .gitignore web/package.json web/package-lock.json web/tsconfig.json web/tsconfig.node.json web/vite.config.ts web/vitest.config.ts web/index.html web/src
git commit -m "feat: scaffold React SPA with /app module routes"
```

### Task 3: Typed API client and error mapping

**Files:**
- Create: `web/src/types/domain.ts`
- Create: `web/src/lib/http.ts`
- Create: `web/src/services/api.ts`
- Create: `web/src/services/api.test.ts`

- [ ] **Step 1: Write failing API service tests**

```ts
it("maps 400 response into user-facing message", async () => {
  mockFetch(400, { detail: "Invalid geometry payload" })
  await expect(createField(payload, { actingUserId: 1 })).rejects.toMatchObject({
    message: "Invalid geometry payload",
    status: 400,
  })
})
```

- [ ] **Step 2: Run API tests and verify fail**

Run: `npm --prefix web test -- --run web/src/services/api.test.ts`
Expected: FAIL because service layer does not exist.

- [ ] **Step 3: Implement fetch wrapper + endpoint functions**

```ts
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

export function listFarms(actingUserId: number) {
  return request<FarmRead[]>("/farms", { headers: { "X-User-Id": String(actingUserId) } })
}
```

- [ ] **Step 4: Re-run API tests**

Run: `npm --prefix web test -- --run web/src/services/api.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add web/src/types/domain.ts web/src/lib/http.ts web/src/services/api.ts web/src/services/api.test.ts
git commit -m "feat: add typed API service layer with error mapping"
```

### Task 4: Users module CRUD UI

**Files:**
- Create: `web/src/features/users/UsersPage.tsx`
- Create: `web/src/features/users/UsersPage.test.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Write failing users-page tests for list/create/update/delete flow**

```tsx
it("creates a user and refreshes table", async () => {
  // mock list -> create -> list invalidation path
  ...
})

it("validates required user fields before submit", async () => {
  // empty name/email/role must show validation and avoid API call
})
```

- [ ] **Step 2: Run users module tests and confirm fail**

Run: `npm --prefix web test -- --run web/src/features/users/UsersPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement users table + form + delete confirmation**

```tsx
const mutation = useMutation({ mutationFn: createUser, onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }) })
```

- [ ] **Step 4: Re-run users tests**

Run: `npm --prefix web test -- --run web/src/features/users/UsersPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add web/src/features/users/UsersPage.tsx web/src/features/users/UsersPage.test.tsx web/src/App.tsx
git commit -m "feat: implement users CRUD module in SPA"
```

### Task 5: Farms module CRUD UI with acting user scope

**Files:**
- Create: `web/src/features/farms/FarmsPage.tsx`
- Create: `web/src/features/farms/FarmsPage.test.tsx`
- Modify: `web/src/components/Layout.tsx`

- [ ] **Step 1: Write failing farms tests including `X-User-Id` handling**

```tsx
it("sends acting user id header when listing farms", async () => {
  // assert service called with selected acting user id
  ...
})

it("validates required farm fields before submit", async () => {
  // empty user_id or name should block mutation
})
```

- [ ] **Step 2: Run farms tests and verify failure**

Run: `npm --prefix web test -- --run web/src/features/farms/FarmsPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement farms CRUD page and acting user selector**

```tsx
<input type="number" value={actingUserId} onChange={...} />
```

- [ ] **Step 4: Re-run farms tests**

Run: `npm --prefix web test -- --run web/src/features/farms/FarmsPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add web/src/features/farms/FarmsPage.tsx web/src/features/farms/FarmsPage.test.tsx web/src/components/Layout.tsx
git commit -m "feat: implement farms CRUD module with acting user scope"
```

### Task 6: Fields module with GeoJSON upload/paste validation

**Files:**
- Create: `web/src/features/fields/geojson.ts`
- Create: `web/src/features/fields/FieldsPage.tsx`
- Create: `web/src/features/fields/FieldsPage.test.tsx`

- [ ] **Step 1: Write failing tests for GeoJSON parsing and field submit flow**

```ts
it("rejects invalid JSON before API call", async () => {
  // paste invalid JSON and expect inline validation error
})

it("accepts Polygon geometry object and posts payload", async () => {
  // upload/textarea valid geometry then submit
})

it("lists existing fields and supports edit/delete", async () => {
  // mock list, update mutation, delete mutation, and cache refresh
})

it("shows friendly message for 404 on refresh", async () => {
  // mock 404 and assert fallback feedback
})

it("validates required field fields before submit", async () => {
  // farm_id, name, and geometry input are mandatory
})

it("loads geometry from .geojson file input", async () => {
  // select file, parse content, populate geometry state, submit success path
})

it("shows validation message for invalid .json upload", async () => {
  // select malformed file and assert parse error + no API call
})
```

- [ ] **Step 2: Run fields tests and verify failure**

Run: `npm --prefix web test -- --run web/src/features/fields/FieldsPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement GeoJSON parser utility and fields full CRUD page**

```ts
export function parseGeometryInput(raw: string): GeoGeometry {
  const parsed = JSON.parse(raw)
  if (parsed.type !== "Polygon" && parsed.type !== "MultiPolygon") {
    throw new Error("GeoJSON geometry must be Polygon or MultiPolygon")
  }
  return parsed as GeoGeometry
}
```

Implementation must include:

- list table for existing fields;
- edit form flow (reuse create form state);
- delete action with confirmation;
- status-aware error message mapping for at least `400` and `404`.
- file input flow (`.geojson`/`.json`) using `File.text()` parse path, with explicit invalid-file error state.

- [ ] **Step 4: Re-run fields tests**

Run: `npm --prefix web test -- --run web/src/features/fields/FieldsPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add web/src/features/fields/geojson.ts web/src/features/fields/FieldsPage.tsx web/src/features/fields/FieldsPage.test.tsx
git commit -m "feat: add fields module with GeoJSON upload and validation"
```

### Task 7: Cross-cutting UX polish and full verification

**Files:**
- Create: `web/src/components/Toast.tsx`
- Create: `web/src/components/ConfirmDialog.tsx`
- Modify: `web/src/features/users/UsersPage.tsx`
- Modify: `web/src/features/farms/FarmsPage.tsx`
- Modify: `web/src/features/fields/FieldsPage.tsx`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests for toasts/loading/error banner interactions**

```tsx
it("shows unavailable banner on 503 responses", async () => {
  // mock 503 and assert banner text
})

it("shows forbidden guidance on 403 responses", async () => {
  // mock 403 and assert actionable message
})

it("shows retry action on unexpected error", async () => {
  // mock network/unexpected failure and assert retry button
})
```

- [ ] **Step 2: Run polish-focused tests and confirm fail**

Run: `npm --prefix web test -- --run`
Expected: at least one FAIL tied to missing toast/banner/confirm behavior.

- [ ] **Step 3: Implement shared UX components and wire all three modules**

```tsx
if (error?.status === 503) return <div role="alert">Backend indisponivel</div>
if (error?.status === 403) return <div role="alert">Acesso negado para este X-User-Id</div>
```

Also include generic fallback with retry button for unexpected failures.

- [ ] **Step 4: Run complete frontend verification**

Run: `npm --prefix web test -- --run && npm --prefix web run build`
Expected: PASS.

- [ ] **Step 5: Run backend verification including new static tests**

Run: `pytest tests/test_web_ui_serving.py tests/test_smoke.py tests/test_routes_registration.py -v`
Expected: PASS.

- [ ] **Step 6: Run broader regression slice for core CRUD contract**

Run: `pytest tests/test_core_crud_api_integration.py -v`
Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```bash
git add web .gitignore README.md tests/test_web_ui_serving.py api/main.py
git commit -m "feat: finalize SPA UX states and integration docs"
```

## Final Verification Checklist

- [ ] `npm --prefix web install`
- [ ] `npm --prefix web test -- --run`
- [ ] `npm --prefix web run build`
- [ ] `pytest -v`
- [ ] Manual smoke:
  - [ ] run API (`uvicorn agro_gee_api.main:app --reload`)
  - [ ] open `http://localhost:8000/app/users`
  - [ ] confirm nav naming matches IA baseline (`Users`, `Farms`, `Geometries`)
  - [ ] validate layout in desktop and narrow mobile viewport
  - [ ] create user, farm, and field with GeoJSON
  - [ ] confirm records list after page refresh

## Notes for Implementer

- Keep MVP strict: no login screen and no role-based UI gates in this cycle.
- Preserve existing API contracts; do not change backend route payload shapes unless a failing test proves incompatibility.
- For farms/fields requests, always send `X-User-Id`; expose a visible acting-user numeric input in UI until auth is introduced.
- Keep components focused and small; if a page exceeds ~250 lines, split form/table sections into local subcomponents.
