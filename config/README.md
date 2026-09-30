# Configuration

All **business configuration** lives in this folder: weights, thresholds, sectors, districts,
languages, LLM / embedding choices and synthetic-data settings. **Python code contains none of
these values.** It reads them through `app.config` (backend/app/config/), which validates
every file with Pydantic when the API starts.

| File | Contents |
|---|---|
| `scoring.yaml` | Demand weights, supply defaults, mismatch thresholds, trend rules, course-health weights and flags, forecast and event-impact settings, recommendation rules, confidence rules, candidate ranking, skill-matching thresholds. **Versioned** (`version:`) and hashed; the hash is stored with every pipeline run. |
| `sectors.yaml` | The prototype's sectors and how event jobs are split across roles |
| `scope.yaml` | State, districts (our internal codes, not official ones), demo district, languages per screen |
| `llm.yaml` | Optional LLM provider, mode, models, tasks; embedding model settings |
| `synthetic.yaml` | Demo-data seed, history quarters, volumes, source IDs, planted patterns, demo event |

## Check your changes

From `backend/` with the virtual environment active:

```powershell
python -m app.config
```

It prints a summary, or **every** problem it finds (wrong sums, unknown keys, missing keys,
values out of range, files that disagree with each other), and exits with code 1. The API
refuses to start with an invalid configuration.

## Rules

- Change `version` in `scoring.yaml` whenever you change a value in it.
- Every key is required, and unknown keys are rejected, so typos are caught.
- Weights that form a total (demand, course health, candidate ranking, staffing shares) must add up to 1.0.
- Never put secrets (API keys) in these files. Use `.env` (`LLM_API_KEY`).
- Never write official government codes here. They go in `data/reference` after verification.

## Environment overrides

A few **environment-specific** switches can override the YAML without editing it. Set them in
`.env` (see `.env.example`) or as environment variables:

| Variable | Overrides |
|---|---|
| `CONFIG_DIR` | Which folder to read (default: this one) |
| `LLM_PROVIDER`, `LLM_MODE`, `LLM_MODEL`, `LLM_MAX_CALLS_PER_JOB` | `llm.yaml` → `llm.*` |
| `LLM_API_KEY` | (secret; never in YAML) |
| `EMBEDDINGS_ENABLED`, `EMBEDDING_MODEL_PATH` | `llm.yaml` → `embeddings.enabled`, `embeddings.local_path` |
| `SYNTH_SEED` | `synthetic.yaml` → `seed` |

Scoring weights and thresholds **cannot** be overridden from the environment on purpose: they
must stay versioned in `scoring.yaml` so every result can be explained.
