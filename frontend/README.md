# KaushalSetu frontend

React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui, TanStack Query, react-router,
Recharts and react-i18next (English / हिन्दी / मराठी).

Setup and run instructions are in the repository [README](../README.md) (section "Demo").

| Command                                   | What it does                                                                                    |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `npm run dev`                             | Dev server at http://localhost:5173 (forwards `/api` and `/health` to the backend on port 8000) |
| `npm run build`                           | Type-check and build into `dist/`                                                               |
| `npm run lint`                            | Lint with oxlint                                                                                |
| `npm run format` / `npm run format:check` | Format / check formatting with Prettier                                                         |
| `npm run test:e2e`                        | Playwright browser tests, including the full demo click path                                    |

## Environment (`frontend/.env.local`, git-ignored)

| Variable             | Default                 | Meaning                                                                         |
| -------------------- | ----------------------- | ------------------------------------------------------------------------------- |
| `VITE_API_TARGET`    | `http://127.0.0.1:8000` | Backend the dev server forwards `/api` and `/health` to                         |
| `VITE_DEMO_EMAIL`    | (unset)                 | Demo account that **Enter demo** signs in with (`python -m app.cli.demo_users`) |
| `VITE_DEMO_PASSWORD` | (unset)                 | Its password. Local demos only: Vite puts it in the built bundle.               |
| `VITE_DEMO_FALLBACK` | `true`                  | `false` turns the demo fallback off: pages show API errors instead              |

## Where data comes from

Every page section shows a badge:

- **Live API + Synthetic**: read from the FastAPI backend. The database holds the synthetic demo
  world, so these are still not real or official statistics.
- **Demo data**: the deterministic fallback in `src/lib/demo/`, used when the API is unreachable,
  the user is not signed in, or the backend has no endpoint for the feature yet.

| Screen                                | Live API                                                                           | Demo fallback                                                    |
| ------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Dashboard, Districts, District detail | `/analytics/demand`, `/mismatch`, `/districts/{d}/mismatch`, `/districts`          | snapshot of the same API (`src/lib/demo/snapshot.json`)          |
| Skills, Skill detail                  | `/analytics/demand?level=skill` (per quarter for trends)                           | snapshot                                                         |
| Courses, Course detail                | skill demand from the API                                                          | course catalogue + course-health score (no backend endpoint yet) |
| Recommendations                       | -                                                                                  | demo recommendations; decisions saved in this browser            |
| Employer portal                       | -                                                                                  | validation, pledges and hiring needs saved in this browser       |
| Career guidance                       | `/analytics/demand?district=` (ranking)                                            | rule-based assistant (no AI model), demo course list             |
| District plans                        | -                                                                                  | Nashik plan, updated by employer pledges/validations             |
| Demo controls                         | `POST /analytics/run`, `/admin/users`, `/admin/audit-log`, `/health`, `/health/db` | reset / simulate stored in this browser                          |
| Sign in                               | `POST /auth/login`, `GET /auth/me`                                                 | offline demo session                                             |

Refresh the snapshot after regenerating the synthetic data (backend running, demo accounts made):

```powershell
$env:DEMO_USER_PASSWORD = "<demo password>"
..\backend\.venv\Scripts\python.exe scripts\snapshot_demo.py
```

## Folders in `src/`

| Folder              | Purpose                                                                               |
| ------------------- | ------------------------------------------------------------------------------------- |
| `app/`              | Providers (query, session, filters), router                                           |
| `pages/`            | One component per screen (`plans/`, `candidate/` hold page parts)                     |
| `components/`       | Shared components: badges, cards, charts, DataTable, FilterBar, overlays, map, states |
| `components/layout` | App shell: sidebar, top bar, breadcrumbs, page titles                                 |
| `components/ui/`    | shadcn/ui components (generated with `npx shadcn@latest add <name>`)                  |
| `lib/api/`          | API client, one service per area, TanStack Query hooks (`queries.ts`)                 |
| `lib/demo/`         | Deterministic demo data, the analytics snapshot and the browser demo store            |
| `i18n/`             | English / Hindi / Marathi UI text                                                     |
