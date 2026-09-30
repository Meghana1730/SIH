# KaushalSetu

Labour-market intelligence and curriculum-alignment platform (Smart India Hackathon prototype).
It connects industry demand → skills → training supply → gaps → curriculum recommendations →
employer validation → outcomes.

> **Status: scaffold + database schema.** The backend, frontend and database run and are
> connected, and the database schema (51 tables, `backend/app/models/`) is in place.
> No product features are built yet. Planning docs are in [`docs/`](docs/).

---

## 1. What you need (install once)

| Tool | Version we tested | Check with |
|---|---|---|
| Windows 11 + PowerShell | — | — |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) (WSL2 backend) | 29.x | `docker version` |
| [Python](https://www.python.org/downloads/) | 3.12 | `py -3.12 --version` |
| [Node.js](https://nodejs.org/) LTS | 22.x (needs ≥ 20.19) | `node -v` |
| [Git](https://git-scm.com/) | 2.x | `git --version` |

Docker Desktop must be **running** (whale icon in the taskbar) before you start the database.

---

## 2. First-time setup

Run these in **PowerShell**, starting in the `kaushalsetu` folder.

### 2.1 Environment file
```powershell
Copy-Item .env.example .env
notepad .env        # change POSTGRES_PASSWORD to any local password, save, close
```
`.env` holds local settings and passwords. It is ignored by git. Never commit it.

You also need a **JWT secret** (it signs login tokens; the API will not start without one).
After step 2.3 below (so Python is set up), generate one and paste it into `.env` as
`JWT_SECRET=<value>`:
```powershell
backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```
Every teammate generates their own; never share or commit it.

### 2.2 Database (PostgreSQL 17 + pgvector, in Docker)
```powershell
docker compose up -d db
docker compose ps          # wait until STATUS shows "(healthy)"
```
The database listens on `127.0.0.1:5433` (not the usual 5432, to avoid clashing with other projects).

### 2.3 Backend (Python / FastAPI)
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # your prompt now starts with (.venv)
pip install -r requirements.lock.txt  # exact versions the team tested
pip install -e . --no-deps            # makes the "app" package importable
alembic upgrade head                  # creates database objects (enables pgvector)
cd ..
```
If `Activate.ps1` is blocked ("running scripts is disabled"), run this once, then try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Optional: semantic skill matching** (needed only if you work on NLP; ~1.5 GB in total).
Without it, skill matching still works with exact / alias / spelling matching.
```powershell
cd backend
pip install -r requirements-embeddings.lock.txt   # PyTorch (CPU) + sentence-transformers
pip install -e ".[embeddings]" --no-deps
python -m app.cli.download_embedding_model        # ONCE: model files into models/ (git-ignored)
cd ..
```
How it works and how well: [docs/05-skill-matching.md](docs/05-skill-matching.md).

**Demo data** (synthetic: fictional institutes/employers, team-assumed numbers, every row
`is_synthetic = true`). Seed the database and prove the planted patterns are in it:
```powershell
cd backend
python -m app.cli.synthetic all        # generate data/synthetic/export + load + validate
python -m app.cli.synthetic validate   # re-check the database at any time (-v = evidence)
cd ..
```
What is in it and why: [docs/SYNTHETIC_DATA_SPEC.md](docs/SYNTHETIC_DATA_SPEC.md).

**Job postings pipeline** (CSV import -> skills -> role -> evidence; the default LLM is a
free mock, no key needed). Copy the synthetic sample to the default input and run it:
```powershell
cd backend
copy ..\data\synthetic\job_postings_sample.csv ..\data\raw\job_postings.csv
python -m app.cli.embed_skills          # vectors for meaning-based matching (once)
python -m app.cli.jobs ingest           # import + process data/raw/job_postings.csv
python -m app.cli.jobs process          # batch: any postings still PENDING
python -m app.cli.jobs evaluate         # precision / recall / role accuracy (gold set)
cd ..
```
API (admin): `POST /api/v1/ingestion/job-postings` and friends. How it works and how
well: [docs/06-job-intelligence.md](docs/06-job-intelligence.md).

### 2.4 Frontend (React / Vite)
```powershell
cd frontend
npm install
npx playwright install chromium       # browser used by the frontend tests (one-time)
cd ..
```

---

## 3. Run the system

Use **two PowerShell windows** (the database already runs in Docker).

**Window 1: backend**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Window 2: frontend**
```powershell
cd frontend
npm run dev
```

Open:

| URL | What you see |
|---|---|
| http://localhost:5173 | The app: a **System status** page. All three rows should say **OK**. |
| http://127.0.0.1:8000/docs | Interactive API documentation (Swagger UI) |
| http://127.0.0.1:8000/health | `{"status":"ok", ...}`: the API is running |
| http://127.0.0.1:8000/health/db | `{"status":"ok","database":"connected","pgvector":{"installed":true,...}}` |

Quick check from PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

---

### Accounts and login

- **Create the first admin** (once per database; the password is asked twice and hidden):
  ```powershell
  cd backend
  .\.venv\Scripts\Activate.ps1
  python -m app.cli.create_user --email admin@example.com --name "Platform Admin" --role admin
  ```
  Other roles need their scope, e.g. `--role district_officer --district MH-NASHIK`.
- **Log in** at http://127.0.0.1:8000/docs: call `POST /api/v1/auth/login`, copy the
  `access_token`, click **Authorize** and paste it. Protected endpoints now work.
- **Who can create accounts:** anyone can sign up, but only as a `candidate` (with consent).
  All staff accounts (officers, institute admins, SSC reviewers, employers, admins) are created by
  an admin via `POST /api/v1/auth/register` while logged in, or with the command above.
- **What each role sees** is defined in one place: `backend/app/services/access.py`
  (e.g. a district officer only sees their own district's institutes and employers).
- Login protection: 5 wrong passwords for one email → 15-minute pause (settings in `.env.example`).

## 4. Stop the system

| To stop | Do this |
|---|---|
| Backend / frontend | Press `Ctrl + C` in their windows |
| Database (keep data) | `docker compose stop` (start again with `docker compose start`) |
| Database container (keep data) | `docker compose down` |
| Database **and delete all its data** | `docker compose down -v`, then redo `alembic upgrade head` after the next start |

---

## 5. Tests and checks

| What | Command (folder) |
|---|---|
| Configuration check (`config/*.yaml`) | `python -m app.config` (in `backend`, venv active); see [config/README.md](config/README.md) |
| Synthetic data: planted patterns | `python -m app.cli.synthetic validate` (database) or `... validate --source export` (files only) |
| Backend tests | `pytest` (in `backend`, venv active) |
| Backend lint / format | `ruff check .` / `black --check .` (in `backend`) |
| Frontend lint / format | `npm run lint` / `npm run format:check` (in `frontend`) |
| Frontend type-check + build | `npm run build` (in `frontend`) |
| Frontend browser tests | `npm run test:e2e` (in `frontend`; starts the dev server itself) |
| **Everything at once** | `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` (repository root) |

Tests marked `db` need the database container running. If it is off, they are **skipped with a
message**, not failed. The Playwright "status checks" test also needs the backend running;
otherwise it is skipped.

Schema tests run against a **separate database, `kaushalsetu_test`**, which pytest creates and
migrates automatically. Every test's changes are rolled back, so your development database is
never touched.

---

## 6. Repository layout

```
kaushalsetu/
├── backend/            FastAPI app, Alembic migrations, pytest tests
│   ├── app/
│   │   ├── main.py     app entry point
│   │   ├── core/       environment settings (.env), database connection
│   │   ├── config/     loads + validates the YAML files in config/
│   │   ├── api/        HTTP routes (health, hello)
│   │   ├── schemas/    request/response models
│   │   ├── models/     database tables (51), grouped by topic
│   │   ├── services/ nlp/ engines/ llm/ bots/ pipelines/   (empty; built later)
│   │   └── evidence.py (placeholder; built later)
│   ├── alembic/        database migrations
│   └── tests/
├── frontend/           React + TypeScript + Vite + Tailwind + shadcn/ui, Playwright tests
├── data/               reference / raw / synthetic / gold / geo / research data
├── config/             business configuration (YAML): weights, thresholds, sectors, districts, LLM
├── docs/               domain primer, PRD, architecture, data plans
├── scripts/            helper scripts (check.ps1)
├── docker-compose.yml  PostgreSQL + pgvector
└── .env.example        template for your local .env
```

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` says **port is already allocated** | Another program uses port 5433. Set `POSTGRES_HOST_PORT=5434` in `.env`, then run `docker compose up -d db` again. |
| `failed to connect to the docker API` | Start Docker Desktop and wait until it says "Engine running". |
| `KaushalSetu cannot start: JWT_SECRET is not set` (or "too short") | Generate a secret (see §2.1) and add `JWT_SECRET=...` to `.env`. |
| Login returns **429 Too many login attempts** | Wait the number of seconds in the `Retry-After` header (default up to 15 minutes), or restart the backend (counters are in memory). |
| `/health/db` returns **503** | The database is not running: `docker compose up -d db`. |
| `/health/db` shows `"installed": false` for pgvector | Run `alembic upgrade head` in `backend` (venv active). |
| After `git pull`: "relation ... does not exist" or a test says the database is behind | Someone added a migration. Run `alembic upgrade head` in `backend`. |
| You changed a model in `app/models/` | Create a migration: `alembic revision --autogenerate -m "what changed"`, review the new file in `alembic/versions/`, then `alembic upgrade head`. The test `test_models_match_migrations` fails if you forget. |
| Database connections are very slow | Use `127.0.0.1`, not `localhost`, in any custom `DATABASE_URL` (Windows tries IPv6 first). |
| `Activate.ps1 cannot be loaded` | See the `Set-ExecutionPolicy` line in §2.3. |
| Frontend shows **Problem** for Backend API | Start the backend (§3, window 1). |
| `npm run dev` says port 5173 is in use | Close the other dev server (or the other Playwright run) and retry. |

---

## 8. Project documents

| Document | What it is |
|---|---|
| [docs/01-domain.md](docs/01-domain.md) | Domain primer: the skilling ecosystem and our terms |
| [docs/03-prd.md](docs/03-prd.md) | MVP product requirements and acceptance criteria |
| [docs/04-architecture.md](docs/04-architecture.md) | Technical architecture |
| [docs/05-skill-matching.md](docs/05-skill-matching.md) | Skill matching: pipeline, model choice, measured results, limits |
| [docs/SYNTHETIC_DATA_SPEC.md](docs/SYNTHETIC_DATA_SPEC.md) | The synthetic demo dataset: honesty rules, planted patterns, commands |
| [docs/06-job-intelligence.md](docs/06-job-intelligence.md) | Job postings pipeline: ingestion, skill/role matching, evidence, LLM guard rails, evaluation |
| [docs/DATA_SOURCE_INVENTORY.md](docs/DATA_SOURCE_INVENTORY.md) | Where data comes from |
| [docs/DATA_COLLECTION_PLAN.md](docs/DATA_COLLECTION_PLAN.md) | Who collects what, and how |
