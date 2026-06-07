# Design: Web UI for Users and GeoJSON Field Registration

## Goal

Add a web UI to the existing project so operators can:

- register and manage users;
- register and manage farms;
- upload/paste GeoJSON geometries and register fields in the database.

The UI must live in the same repository and be served by FastAPI.

## Scope

In scope:

- New React SPA (TypeScript + Vite) inside this repository.
- FastAPI static hosting for SPA build output.
- CRUD UI for users (`/users`).
- CRUD UI for farms (`/farms`).
- Field creation/update UI using GeoJSON for geometry (`/fields`).
- Basic client-side validation and clear API error handling.

Out of scope:

- Authentication and authorization in the UI (MVP without login).
- Support for geometry formats beyond GeoJSON.
- Redesign of existing API contracts.

## Constraints and Decisions

- Chosen approach: SPA (`Option C`) for long-term flexibility.
- Deployment model: same FastAPI project serves both API and frontend artifacts.
- Geo format: GeoJSON only (`.geojson` / `.json` file input or pasted JSON).
- Farm flow: include farm management UI, not only numeric `farm_id` entry.
- Access model: no login in this MVP.

## Architecture

### Frontend

- New folder: `web/`.
- Stack: React + Vite + TypeScript.
- Routing: client-side routes under `/app`, with explicit module paths:
  - `/app/users`
  - `/app/farms`
  - `/app/fields`
- Data layer: centralized API service module + query/cache layer for list invalidation.

### Backend integration

- FastAPI keeps existing API routes unchanged.
- FastAPI serves built SPA static files (from `web/dist`) and a fallback entry page for SPA routes.
- API endpoints remain under current paths (`/users`, `/farms`, `/fields`).

## Functional Design

### Users module

- List users in table.
- Create user.
- Edit user.
- Delete user with confirmation.

Fields in form:

- `name` (required)
- `email` (required, basic format validation)
- `role` (required)
- `parent_user_id` (optional)

### Farms module

- List farms in table.
- Create farm.
- Edit farm.
- Delete farm with confirmation.

Fields in form:

- `user_id` (required)
- `name` (required)
- `location` (optional)

### Fields/Geometries module

- List fields in table.
- Create field using farm selection + name + GeoJSON geometry.
- Edit field with same geometry flow.
- Delete field with confirmation.

Geometry input UX:

- upload local `.geojson` / `.json` file, or
- paste raw GeoJSON text.

Client pre-checks:

- valid JSON parse;
- required GeoJSON object shape present.

API contract alignment for field submit payload:

- frontend sends `geometry` as a GeoJSON geometry object compatible with backend (`Polygon` or `MultiPolygon`), not a full `FeatureCollection` envelope.
- example shape:

```json
{
  "type": "Polygon",
  "coordinates": [[[-47.1, -15.8], [-47.0, -15.8], [-47.0, -15.7], [-47.1, -15.7], [-47.1, -15.8]]]
}
```

Server remains source of truth for geometry validity (PostGIS validation and constraints).

## Data Flow

1. User opens module page (`users`, `farms`, `fields`).
2. Frontend fetches list from API and renders table.
3. On create/update/delete, frontend calls endpoint and invalidates relevant list query.
4. UI shows optimistic loading state and completion toast.
5. On API error, UI maps status code/message into user-facing feedback.

## Error Handling

- `400`: show backend validation message (e.g., invalid geometry payload).
- `404`: show not found message and allow refresh.
- `403`: show forbidden message (for future auth compatibility).
- `503`: global banner for backend unavailable.
- Unexpected errors: generic fallback message with retry action.

## UX Baseline

- Three primary sections in navigation: Users, Farms, Geometries.
- Responsive layout for desktop and mobile.
- Loading states in list and form actions.
- Success/error toast feedback.
- Explicit delete confirmation.

## Testing Strategy

Backend:

- Keep existing test suite passing.
- Add/adjust backend tests only if static serving introduces new behavior.

Frontend:

- Smoke tests for each module route rendering.
- API service tests with mocked HTTP responses for success and error mappings.
- Form validation tests for required fields and invalid GeoJSON input.

## Delivery Phases

1. Scaffold SPA (`web/`) and FastAPI static integration.
2. Implement users module.
3. Implement farms module.
4. Implement fields/geometries module with GeoJSON upload/paste.
5. Add polish (toasts, loading, error banners) and run test/quality checks.

## Risks and Mitigations

- Risk: API/client contract drift during UI build.
  - Mitigation: central typed API service and endpoint-aligned payload models.
- Risk: invalid/malformed geometry reaches backend frequently.
  - Mitigation: early client parse checks + clear server-side error rendering.
- Risk: no-login MVP accidentally exposed in production.
  - Mitigation: keep auth-ready architecture and gate production rollout with environment-level access control.
