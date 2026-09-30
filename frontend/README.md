# KaushalSetu frontend

React + TypeScript + Vite + Tailwind CSS + shadcn/ui.

Setup and run instructions are in the repository [README](../README.md).

| Command                                   | What it does                                                                                    |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `npm run dev`                             | Dev server at http://localhost:5173 (forwards `/api` and `/health` to the backend on port 8000) |
| `npm run build`                           | Type-check and build into `dist/`                                                               |
| `npm run lint`                            | Lint with oxlint                                                                                |
| `npm run format` / `npm run format:check` | Format / check formatting with Prettier                                                         |
| `npm run test:e2e`                        | Playwright browser tests (starts the dev server automatically)                                  |

Folders in `src/`:

| Folder           | Purpose                                                                                |
| ---------------- | -------------------------------------------------------------------------------------- |
| `app/`           | App shell (later: routing, providers, role guards)                                     |
| `pages/`         | One component per screen                                                               |
| `components/ui/` | shadcn/ui components (generated with `npx shadcn@latest add <name>`, do not hand-edit) |
| `lib/`           | Helpers (`utils.ts` from shadcn, `api.ts` for backend calls)                           |
| `i18n/`          | English / Hindi / Marathi text (not set up yet)                                        |
| `maps/`          | District map (not set up yet)                                                          |
