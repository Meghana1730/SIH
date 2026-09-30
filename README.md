# InnovProcure

Labour-market intelligence and curriculum-alignment platform (Smart India Hackathon prototype).
It connects industry demand → skills → training supply → gaps → curriculum recommendations →
employer validation → outcomes.

> **Status: working prototype on synthetic demo data.** The synthetic demo world, the job-posting
> intelligence pipeline, the demand → supply → mismatch engine and the web app (dashboard,
> districts, skills, course health, recommendations, employer portal, career guidance, district
> plans) run end to end. **All data is synthetic demo data, not real or official statistics.**
> Planning docs are in [`docs/`](docs/).

Inside the code, database, demo accounts and error messages the project still uses its earlier
working name **KaushalSetu** (e.g. `kaushalsetu-db`, `admin@kaushalsetu.example`).

**Contents:** [1. Install once](#1-install-these-tools-once) ·
[2. First-time setup](#2-first-time-setup-once-per-computer) ·
[3. Run it](#3-run-it-every-time) · [4. Stop it](#4-stop-it) ·
[5. Optional extras](#5-optional-extras) · [6. Tests](#6-tests-and-checks) ·
[7. Layout](#7-repository-layout) · [8. Troubleshooting](#8-troubleshooting) ·
[9. Documents](#9-project-documents) · [10. Deploy online](#10-deploy-online-free)

---

## 1. Install these tools once

| Tool | Version we tested | Check with |
|---|---|---|
| Windows 11 + PowerShell | — | — |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.x (WSL2 backend; the installer may enable WSL and ask for a restart) | Engine 29.x | `docker version` |
| [Python 3.12](https://www.python.org/downloads/windows/): pick a **3.12.x** "Windows installer (64-bit)", not the newest version; tick "Add python.exe to PATH" and keep "py launcher" ticked | 3.12 (required: the commands use `py -3.12`) | `py -3.12 --version` |
| [Node.js](https://nodejs.org/) LTS | 22.x (needs 20.19+ or 22.12+) | `node -v` |
| [Git](https://git-scm.com/) | 2.x | `git --version` |

Start **Docker Desktop** and wait until it says "Engine running" before step 3 below.

---

## 2. First-time setup (once per computer)

Run everything in **PowerShell**. Each block starts in the **repository folder** (the folder
with this README) and ends there again.

**Step 0. Allow PowerShell to run local scripts** (once per Windows user; Windows PowerShell
blocks `Activate.ps1` and `npm.ps1` by default)
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned   # answer Y if asked
```
Then close PowerShell and open a new window.

**Step 1. Get the code** (into a local folder, not one synced by OneDrive such as Documents or
Desktop: OneDrive makes `npm install` and `pip install` slow and can lock files)
```powershell
cd C:\
git clone https://github.com/Meghana1730/SIH.git
cd SIH
```

**Step 2. Create your settings file `.env`** (ignored by git; never commit it)
```powershell
Copy-Item .env.example .env
# Fill in JWT_SECRET (signs login tokens; the API refuses to start without it):
$jwt = py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env) -replace '^JWT_SECRET=.*', "JWT_SECRET=$jwt" | Set-Content -Encoding ascii .env
if (Select-String -Path .env -Pattern '^JWT_SECRET=.{32,}') { 'JWT_SECRET OK' } else { 'JWT_SECRET missing: install Python 3.12, then redo this step' }
notepad .env        # set POSTGRES_PASSWORD (letters, digits, - and _ only), press Ctrl+S, close
```
Set `POSTGRES_PASSWORD` **before** step 3: the database is created with it the first time.

**Step 3. Start the database** (PostgreSQL 17 + pgvector in Docker)
```powershell
docker compose up -d --wait db   # returns when the database is healthy
```
It listens on `127.0.0.1:5433` (not the usual 5432, to avoid clashing with other projects) and
starts again by itself when Docker Desktop starts, unless you stopped it with
`docker compose stop` or `docker compose down`.

**Step 4. Backend: install it and create the database tables**
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # your prompt now starts with (.venv)
pip install -r requirements.lock.txt  # exact versions the team tested
pip install -e . --no-deps            # makes the "app" package importable
alembic upgrade head                  # creates the tables (and enables pgvector)
cd ..
```
This takes a few minutes the first time. pip's "A new release of pip is available" notice is
harmless.

**Step 5. Load the demo data and compute the analytics**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1          # skip if your prompt already shows (.venv)
python -m app.cli.synthetic load      # the synthetic demo world (fictional, is_synthetic = true)
python -m app.cli.synthetic validate  # checks the planted patterns are in the database
python -m app.cli.analytics run       # demand -> supply -> mismatch for all 4 districts
cd ..
```

**Step 6. Create the demo accounts** (one per role; you choose the password)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1          # skip if your prompt already shows (.venv)
$env:DEMO_USER_PASSWORD = 'choose-a-demo-password'   # 10-128 characters: letters, digits, - and _ only
python -m app.cli.demo_users
# Lets "Enter demo" sign in to your local API by itself (git-ignored; never commit it):
"VITE_DEMO_EMAIL=admin@kaushalsetu.example`nVITE_DEMO_PASSWORD=$env:DEMO_USER_PASSWORD" | Set-Content -Encoding ascii ..\frontend\.env.local
cd ..
```
This creates `admin@`, `state@`, `nashik@`, `institute@`, `employer@` and `candidate@kaushalsetu.example`,
all with that password, and writes `frontend\.env.local`. The password is never stored in the code.
Without `frontend\.env.local`, **Enter demo** still works, in offline demo mode with built-in demo
data (every screen then says **Demo data**).

**Step 7. Frontend: install it**
```powershell
cd frontend
npm ci                                # exact versions from package-lock.json
npx playwright install chromium       # optional: the browser for the frontend tests (npm run test:e2e)
cd ..
```

---

## 3. Run it (every time)

Start Docker Desktop and wait until it says "Engine running". Then open **two PowerShell
windows** in the repository folder.

**Window 1: database + backend**
```powershell
docker compose up -d db               # starts the database if needed (safe to repeat)
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Window 2: frontend**
```powershell
cd frontend
npm run dev
```

Open **http://localhost:5173** and click **Enter demo**.

| URL | What you see |
|---|---|
| http://localhost:5173 | The app: **Enter demo**, or sign in with a demo account from step 6 |
| http://localhost:5173/status | System status: all three rows should say **OK** |
| http://127.0.0.1:8000/docs | Interactive API documentation (Swagger UI) |
| http://127.0.0.1:8000/health | `{"status":"ok", ...}`: the API is running |
| http://127.0.0.1:8000/health/db | `{"status":"ok","database":"connected","pgvector":{"installed":true,...}}` |

Every screen marks where its numbers come from: **Live API** (+ **Synthetic**, because the
database holds the synthetic demo world) or **Demo data** (the frontend's built-in fallback for
features the backend does not have yet). See [frontend/README.md](frontend/README.md).

**Demo walkthrough (5 minutes):** Dashboard → **Investigate Nashik** → EV Diagnostics skill card →
Electrician course at Example ITI A (42/100, at risk) → recommendation "Add an EV Diagnostics
module" (priority 91) → **Ask employers to validate** → agree + pledge 35 apprenticeship seats →
**District Plans** (the Nashik plan now shows the 35 seats). The **Help** page in the app has the
same walkthrough with links.

**After `git pull`** (teammates may have changed dependencies, migrations or demo data):
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
alembic upgrade head
python -m app.cli.synthetic load      # only if data/synthetic/ changed
python -m app.cli.analytics run       # only if data/synthetic/ or config/ changed
cd ..\frontend
npm ci
cd ..
```

---

## 4. Stop it

Run `docker compose` commands in the repository folder.

| To stop | Do this |
|---|---|
| Backend / frontend | Press `Ctrl + C` in their windows |
| Database (keep data) | `docker compose stop`; start again with `docker compose up -d db` (it does not start by itself with Docker Desktop until you do) |
| Database container (keep data) | `docker compose down`; start again with `docker compose up -d db` |
| Database **and delete all its data** | `docker compose down -v`; after the next `docker compose up -d --wait db`, redo steps 4 (`alembic upgrade head`), 5 and 6 |

---

## 5. Optional extras

**Semantic skill matching** (needed only if you work on NLP; ~1.5 GB in total).
Without it, skill matching still works with exact / alias / spelling matching.
```powershell
cd backend
.\.venv\Scripts\Activate.ps1                      # skip if your prompt already shows (.venv)
pip install -r requirements-embeddings.lock.txt   # PyTorch (CPU) + sentence-transformers
python -m app.cli.download_embedding_model        # ONCE: model files into models/ (git-ignored)
python -m app.cli.embed_skills                    # ONCE after the download: vectors for the skill vocabulary
cd ..
```
How it works and how well: [docs/05-skill-matching.md](docs/05-skill-matching.md).

**Regenerate the synthetic data** (only if you change `data/synthetic/spec/demo_world.yaml` or
`config/synthetic.yaml`; the export in git is already up to date):
```powershell
cd backend
.\.venv\Scripts\Activate.ps1           # skip if your prompt already shows (.venv)
python -m app.cli.synthetic all        # generate data/synthetic/export + load + validate
python -m app.cli.analytics run        # recompute the analytics on the new data
cd ..
```
What is in it and why: [docs/SYNTHETIC_DATA_SPEC.md](docs/SYNTHETIC_DATA_SPEC.md).

**Job postings pipeline** (CSV import -> skills -> role -> evidence; the default LLM is a
free mock, no key needed; meaning-based matching is used only if you installed the semantic
extra above). Copy the synthetic sample to the default input and run it:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1            # skip if your prompt already shows (.venv)
Copy-Item ..\data\synthetic\job_postings_sample.csv ..\data\raw\job_postings.csv
python -m app.cli.jobs ingest           # import + process data/raw/job_postings.csv
python -m app.cli.jobs process          # batch: any postings still PENDING
python -m app.cli.jobs evaluate         # precision / recall / role accuracy (gold set)
cd ..
```
API (admin): `POST /api/v1/ingestion/job-postings` and friends. How it works and how
well: [docs/06-job-intelligence.md](docs/06-job-intelligence.md).

**Analytics from the command line:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1            # skip if your prompt already shows (.venv)
python -m app.cli.analytics show --district MH-NASHIK --role ev-service-technician
python -m app.cli.analytics validate    # the planted synthetic patterns are found
cd ..
```
API: `GET /api/v1/analytics/demand|supply|mismatch`, `.../districts/{district}/mismatch`.
Formulas and explanations: [docs/07-demand-supply-mismatch.md](docs/07-demand-supply-mismatch.md).

**Accounts and login**

- **Create more accounts** (the password is asked twice and hidden):
  ```powershell
  cd backend
  .\.venv\Scripts\Activate.ps1
  python -m app.cli.create_user --email admin@example.com --name "Platform Admin" --role admin
  ```
  Other roles need their scope, e.g. `--role district_officer --district MH-NASHIK`.
- **Log in to the API directly** at http://127.0.0.1:8000/docs: call `POST /api/v1/auth/login`,
  copy the `access_token`, click **Authorize** and paste it. Protected endpoints now work.
- **Who can create accounts:** anyone can sign up, but only as a `candidate` (with consent).
  All staff accounts (officers, institute admins, SSC reviewers, employers, admins) are created by
  an admin via `POST /api/v1/auth/register` while logged in, or with the command above.
- **What each role sees** is defined in one place: `backend/app/services/access.py`
  (e.g. a district officer only sees their own district's institutes and employers).
- Login protection: 5 wrong passwords for one email → 15-minute pause (settings in `.env.example`).

---

## 6. Tests and checks

| What | Command (folder) |
|---|---|
| Configuration check (`config/*.yaml`) | `python -m app.config` (in `backend`, venv active); see [config/README.md](config/README.md) |
| Synthetic data: planted patterns | `python -m app.cli.synthetic validate` (database) or `... validate --source export` (files only) |
| Backend tests | `pytest` (in `backend`, venv active) |
| Backend lint / format | `ruff check .` / `black --check .` (in `backend`, venv active) |
| Frontend lint / format | `npm run lint` / `npm run format:check` (in `frontend`) |
| Frontend type-check + build | `npm run build` (in `frontend`) |
| Frontend browser tests | `npm run test:e2e` (in `frontend`; first time: `npx playwright install chromium`; starts the dev server itself) |
| **Everything at once** | `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` (repository root) |

Tests marked `db` need the database container running. If it is off, they are **skipped with a
message**, not failed. The Playwright "status checks" test also needs the backend running;
otherwise it is skipped.

Schema tests run against a **separate database, `kaushalsetu_test`**, which pytest creates and
migrates automatically. Every test's changes are rolled back, so your development database is
never touched.

---

## 7. Repository layout

```
SIH/  (repository root)
├── backend/            FastAPI app, Alembic migrations, pytest tests
│   ├── app/
│   │   ├── main.py     app entry point
│   │   ├── core/       environment settings (.env), database connection, security
│   │   ├── config/     loads + validates the YAML files in config/
│   │   ├── api/        HTTP routes (auth, admin, directory, ingestion, analytics, health)
│   │   ├── schemas/    request/response models
│   │   ├── models/     database tables (52), grouped by topic
│   │   ├── services/   access rules, auth, audit log
│   │   ├── synthetic/  synthetic demo-world generator, loader and checks
│   │   ├── jobs/       job-posting ingestion, processing, evaluation
│   │   ├── nlp/        skill extraction, skill and role matching
│   │   ├── llm/        LLM client (mock by default) with guard rails
│   │   ├── analytics/  demand → supply → mismatch engine
│   │   ├── cli/        command-line tools (python -m app.cli.<name>)
│   │   └── engines/ bots/ pipelines/ evidence.py   (placeholders; built later)
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

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose up` says **port is already allocated** | Another program uses port 5433. Set `POSTGRES_HOST_PORT=5434` in `.env`, then run `docker compose up -d db` again. |
| `failed to connect to the docker API` | Start Docker Desktop and wait until it says "Engine running". |
| `KaushalSetu cannot start: JWT_SECRET is not set` (or "too short") | Fill in `JWT_SECRET` in `.env` (setup step 2). |
| Login returns **429 Too many login attempts** | Wait the number of seconds in the `Retry-After` header (default up to 15 minutes), or restart the backend (counters are in memory). |
| `/health/db` returns **503** | The database is not running: `docker compose up -d db`. |
| `/health/db` shows `"installed": false` for pgvector | Run `alembic upgrade head` in `backend` (venv active). |
| After `git pull`: "relation ... does not exist" or a test says the database is behind | Someone added a migration. Run `alembic upgrade head` in `backend`. |
| You changed a model in `app/models/` | Create a migration: `alembic revision --autogenerate -m "what changed"`, review the new file in `alembic/versions/`, then `alembic upgrade head`. The test `test_models_match_migrations` fails if you forget. |
| Database connections are very slow | Use `127.0.0.1`, not `localhost`, in any custom `DATABASE_URL` (Windows tries IPv6 first). |
| `Activate.ps1` or `npm.ps1` cannot be loaded ("running scripts is disabled") | Run setup step 0, open a new PowerShell window and try again. |
| `alembic`, `synthetic load` or the backend says **password authentication failed for user "kaushal"** | `POSTGRES_PASSWORD` in `.env` was changed after the database was first created (step 3). Put the old password back, or wipe the database: `docker compose down -v`, `docker compose up -d --wait db`, then redo steps 4-6. |
| Frontend shows **Problem** for Backend API | Start the backend (section 3, window 1). |
| `npm run dev` says port 5173 is in use | Close the other dev server (or the other Playwright run) and retry. |
| Every screen says **Demo data** instead of **Live API** | The frontend is not signed in to the API. Check that the backend runs (window 1), that `frontend\.env.local` exists and its `VITE_DEMO_PASSWORD=` line is not empty (setup step 6), then restart `npm run dev`, sign out (top-right menu) and click **Enter demo** again. |
| Dashboard says "No analytics results yet" or shows demo data only | Run `python -m app.cli.analytics run` in `backend` (setup step 5). |
| `demo_users` says "Password must be at least 10 characters" | Choose a longer `DEMO_USER_PASSWORD` (setup step 6). |
| Signing in with a demo account fails | The password in `frontend\.env.local` must match the one used in setup step 6 (existing accounts are never changed). Correct `.env.local` and restart `npm run dev`. If you forgot the password, delete the demo accounts and redo step 6: `docker compose exec db psql -U kaushal -d kaushalsetu -c "DELETE FROM app_user WHERE is_demo"` (in the repository folder). |
| `synthetic load` says the export is out of date | Someone changed the spec: run `python -m app.cli.synthetic all` (section 5). |
| `pip install` fails to build packages | Make sure the venv uses Python 3.12 (`python --version` inside the venv); recreate it with `py -3.12 -m venv .venv`. |

---

## 9. Project documents

| Document | What it is |
|---|---|
| [docs/01-domain.md](docs/01-domain.md) | Domain primer: the skilling ecosystem and our terms |
| [docs/03-prd.md](docs/03-prd.md) | MVP product requirements and acceptance criteria |
| [docs/04-architecture.md](docs/04-architecture.md) | Technical architecture |
| [docs/05-skill-matching.md](docs/05-skill-matching.md) | Skill matching: pipeline, model choice, measured results, limits |
| [docs/SYNTHETIC_DATA_SPEC.md](docs/SYNTHETIC_DATA_SPEC.md) | The synthetic demo dataset: honesty rules, planted patterns, commands |
| [docs/06-job-intelligence.md](docs/06-job-intelligence.md) | Job postings pipeline: ingestion, skill/role matching, evidence, LLM guard rails, evaluation |
| [docs/07-demand-supply-mismatch.md](docs/07-demand-supply-mismatch.md) | Demand score, training supply, estimated openings and mismatch: formulas, API, explanations, results |
| [docs/08-deployment.md](docs/08-deployment.md) | Deploy online for free: Vercel (frontend) + Render (backend) + Neon (database) |
| [docs/REVIEW_FINDINGS_JOB_PIPELINE.md](docs/REVIEW_FINDINGS_JOB_PIPELINE.md) | Verified code-review findings still open for the job pipeline and synthetic data |
| [docs/DATA_SOURCE_INVENTORY.md](docs/DATA_SOURCE_INVENTORY.md) | Where data comes from |
| [docs/DATA_COLLECTION_PLAN.md](docs/DATA_COLLECTION_PLAN.md) | Who collects what, and how |

---

## 10. Deploy online (free)

The website runs for Rs 0 on three free services:

| Part | Service | Config in this repository |
|---|---|---|
| Frontend (the website) | **Vercel** | [`frontend/vercel.json`](frontend/vercel.json): serves deep links; forwarding `/api` to the backend is added when the backend is live (guide step 4) |
| Backend API | **Render** (free Docker web service) | [`render.yaml`](render.yaml), [`backend/Dockerfile`](backend/Dockerfile) |
| Database (PostgreSQL + pgvector) | **Neon** (free plan) | filled from your laptop with the setup commands |

Step-by-step guide, judging-day tips and troubleshooting: **[docs/08-deployment.md](docs/08-deployment.md)**.
