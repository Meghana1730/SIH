# Synthetic demo data

**Everything in this folder is SYNTHETIC** (fictional institutes and employers, team-assumed
numbers). It is never an official statistic. Every row has `is_synthetic = true`.

| Path | What |
|---|---|
| `spec/demo_world.yaml` | The hand-written demo world (edit this) |
| `export/` | Generated files: one CSV per database table, `manifest.json`, `summary.json` (do not edit by hand; a hash check refuses edited files) |

Regenerate, load and validate from `backend/` (venv active):

```powershell
python -m app.cli.synthetic all
```

The CSV headers are the database column names (`source` holds the source ID, e.g. `Y01`).
Details, planted patterns and limitations: [docs/SYNTHETIC_DATA_SPEC.md](../../docs/SYNTHETIC_DATA_SPEC.md).
