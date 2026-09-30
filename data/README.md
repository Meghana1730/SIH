# Data folders

Rules for all data are in [`docs/DATA_COLLECTION_PLAN.md`](../docs/DATA_COLLECTION_PLAN.md).
Every CSV must carry the provenance columns (`source_id`, `source_ref`, `fetched_at`,
`license_note`, `is_synthetic`) and be saved as **UTF-8** (Excel: *Save As → CSV UTF-8*).

| Folder | What goes here | In git? |
|---|---|---|
| `reference/` | Curated real reference data: districts, roles, skills, courses, QPs, equipment | Yes |
| `raw/` | Original downloads (PDFs, Excel), untouched, one sub-folder per source ID | **No** (only `raw/README.md`) |
| `synthetic/` | Generated demo data, every row `is_synthetic=true` | Yes |
| `gold/` | Hand-labelled postings for testing skill extraction | Yes |
| `geo/` | Simplified district boundary files for the map | Yes |
| `research/` | `source_inventory` tracker (see `docs/DATA_SOURCE_INVENTORY.md`) | Yes |

The only data loaded so far is the **synthetic demo dataset** (`synthetic/`, see
[`docs/SYNTHETIC_DATA_SPEC.md`](../docs/SYNTHETIC_DATA_SPEC.md)). No real data has been loaded yet.
