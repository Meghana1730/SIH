# Skill matching (v1): how it works and how well it does

| | |
|---|---|
| **Audience** | The whole team, especially whoever builds the job-posting pipeline next |
| **Code** | `backend/app/nlp/` (`text.py`, `embeddings.py`, `skill_embeddings.py`, `skill_matcher.py`, `evaluation.py`) |
| **Config** | `config/scoring.yaml` → `skill_matching`; `config/llm.yaml` → `embeddings`, `tasks.skill_match_fallback` |
| **Measured on** | 2026-09-29, `data/gold/skill_matching_cases.yaml` (44 phrases, 17 synthetic skills) |

> **Honesty first:** semantic similarity is *not* certainty. The matcher returns a confidence
> and the method it used, and anything uncertain goes to a **human review queue**. The numbers
> below come from a small, hand-made test set. Expect them to drop on the real vocabulary
> (150–300 skills: more near neighbours to confuse).

---

## 1. What it does

It takes a free-text phrase (e.g. from a job ad or survey), such as *"EV troubleshooting"*, and
finds the skill in our vocabulary it most likely means, such as **EV Diagnostics**:

```json
{
  "input": "EV troubleshooting",
  "matched_skill": "EV Diagnostics",
  "matched_text": "EV fault diagnosis",
  "confidence": 0.809,
  "method": "embedding",
  "decision": "review",
  "similarity": 0.943,
  "alternatives": [{"skill": "EV Battery Testing", "score": 0.779, "method": "embedding"}]
}
```

`decision` is **accept** (confidence ≥ 0.85), **review** (≥ 0.60, a human checks it) or
**no_match**. Here the result is *review* because the runner-up (EV Battery Testing) is close:
exactly the kind of case a human should confirm.

## 2. The pipeline (cheapest and most certain step first)

| Step | What it checks | Confidence | Example |
|---|---|---|---|
| 1. **exact** | Normalised text = a skill name | 1.0 | "pLc  programming" → PLC Programming |
| 2. **alias** | Normalised text = a curated alias (any language) | `alias_confidence` (1.0) | "सोलर पैनल लगाना" → Rooftop Solar PV Installation |
| 3. **fuzzy** | Spelling variant (rapidfuzz token-sort ratio ≥ `fuzzy.min_score` 0.88) | the spelling similarity | "Transformer Maintainance" → Transformer Maintenance |
| 4. **embedding** | Closest *meaning* (sentence embeddings, pgvector cosine search over names + aliases) | calibrated similarity (see §4) | "wiring of homes" → Domestic Wiring |
| 5. **llm** (optional, off) | An LLM may only **pick one of the candidates** above | capped at 0.80 → always *review* | not enabled in the MVP |

Design rules:
- **Normalisation** (lower-case, Unicode NFC, punctuation → space) keeps Devanagari vowel signs.
  A naive "letters only" rule would break Hindi and Marathi words.
- **Fuzzy near-misses never decide a match.** "Accounting" looks a bit like "grounding" (0.63)
  but that says nothing about meaning. Such candidates are only listed as alternatives.
- **The LLM never runs on every match** and can never invent a skill. It is disabled
  (`llm.yaml: mode off`, `tasks.skill_match_fallback.enabled: false`), and only a hook exists.
- **Vectors are tagged with their "space"** (model + text prefix). Search only compares vectors
  from the same space, so changing the model can never mix incompatible numbers.
- **Without embeddings** (not installed, model not downloaded, or `EMBEDDINGS_ENABLED=false`),
  steps 1–3 still work and step 4 is skipped with a note.

## 3. Choosing the model

Both 384-dimension candidates from the architecture document were downloaded and compared on
the same phrases (raw cosine similarity, best vocabulary entry per phrase):

| | `intfloat/multilingual-e5-small` ("query:" on both sides) | `paraphrase-multilingual-MiniLM-L12-v2` |
|---|---|---|
| Right skill ranked first: semantic (15) | **15/15** (incl. all 3 Hindi/Marathi) | 14/15 (Hindi EV phrase → wrong skill, near-tie) |
| Right skill ranked first: spelling (8) | 8/8 | 7/8 |
| Similarity of correct matches | 0.871 – 0.988 | 0.527 – 0.969 |
| Best similarity of **unrelated** phrases | 0.830 – 0.881 | 0.171 – 0.496 |

**Chosen: e5-small.** It ranks better, especially across languages, which matters for Hindi and
Marathi. Its drawback is **compressed scores**: even "Cooking" scores 0.87 against our skills, so
raw similarity cannot be used as confidence directly. The "query:" prefix on both sides follows
the model card's advice for symmetric tasks, and ranked better than "query:"/"passage:" here.

## 4. Calibration

`confidence = (similarity − floor) / (1 − floor)`, clipped to 0..1, with
`llm.yaml → embeddings.similarity_floor = 0.70`. With the review/accept thresholds from
`scoring.yaml`, that means:

| Raw cosine similarity | Confidence | Decision |
|---|---|---|
| ≥ ~0.955 | ≥ 0.85 | accept |
| ~0.88 – 0.955 | 0.60 – 0.85 | review |
| < ~0.88 | < 0.60 | no match |

The floor was chosen by looking at this small test set. It is a **starting point, not a
proven value**: re-check it on the real vocabulary and gold-labelled postings.

## 5. Measured results

### Full pipeline

| Category | Cases | With embeddings (e5-small, floor 0.70) | Without embeddings (steps 1–3 only) |
|---|---|---|---|
| exact | 5 | 5 correct accept | 5 correct accept |
| alias | 6 | 6 correct accept | 6 correct accept |
| spelling | 8 | 8 correct accept | 8 correct accept |
| semantic | 15 | 7 correct accept, 7 correct review, **1 missed** | 2 correct accept, 13 missed |
| unrelated | 10 | 9 rejected, **1 false review** | 10 rejected |

- Right skill found (accepted or sent to review): **97%** with embeddings, 62% without.
- Precision of automatic accepts: **100%** (no wrong skill was ever auto-accepted).
- Wrong skill assigned: **0**. Unrelated phrases auto-accepted: **0**.

### Every case (with embeddings)

| Input | Expected | Result | Method | Confidence | Outcome |
|---|---|---|---|---|---|
| EV Diagnostics | ev-diagnostics | EV Diagnostics | exact | 1.00 | correct accept |
| pLc programming | plc-programming | PLC Programming | exact | 1.00 | correct accept |
| Domestic   Wiring | domestic-wiring | Domestic Wiring | exact | 1.00 | correct accept |
| High Voltage Safety | hv-safety | High-Voltage Safety | exact | 1.00 | correct accept |
| Motor Rewinding. | motor-rewinding | Motor Rewinding | exact | 1.00 | correct accept |
| HV safety | hv-safety | High-Voltage Safety | alias | 1.00 | correct accept |
| House Wiring | domestic-wiring | Domestic Wiring | alias | 1.00 | correct accept |
| EV charging station installation | ev-charger-installation | EV Charger Installation | alias | 1.00 | correct accept |
| सोलर पैनल लगाना | rooftop-solar-installation | Rooftop Solar PV Installation | alias | 1.00 | correct accept |
| lockout/tagout | electrical-safety | Electrical Safety Procedures | alias | 1.00 | correct accept |
| programmable logic controller programming | plc-programming | PLC Programming | alias | 1.00 | correct accept |
| EV diagnostcs | ev-diagnostics | EV Diagnostics | fuzzy | 0.96 | correct accept |
| Domestic Wirring | domestic-wiring | Domestic Wiring | fuzzy | 0.97 | correct accept |
| Multimetre Measurement | multimeter-measurement | Multimeter Measurement | fuzzy | 0.95 | correct accept |
| rooftop solar PV instalation | rooftop-solar-installation | Rooftop Solar PV Installation | fuzzy | 0.98 | correct accept |
| PLC programing | plc-programming | PLC Programming | fuzzy | 0.97 | correct accept |
| high-voltage safty | hv-safety | High-Voltage Safety | fuzzy | 0.97 | correct accept |
| Motor rewindng | motor-rewinding | Motor Rewinding | fuzzy | 0.97 | correct accept |
| Transformer Maintainance | transformer-maintenance | Transformer Maintenance | fuzzy | 0.94 | correct accept |
| EV troubleshooting | ev-diagnostics | EV Diagnostics | embedding | 0.81 | correct review |
| electric vehicle diagnostics | ev-diagnostics | EV Diagnostics | embedding | 0.87 | correct accept |
| EV diagnostic | ev-diagnostics | EV Diagnostics | fuzzy | 0.96 | correct accept |
| diagnosing electric vehicle faults | ev-diagnostics | EV Diagnostics | embedding | 0.91 | correct accept |
| installing EV chargers | ev-charger-installation | EV Charger Installation | fuzzy | 0.89 | correct accept |
| mounting solar panels on roofs | rooftop-solar-installation | Rooftop Solar PV Installation | embedding | 0.71 | correct review |
| testing lithium-ion battery packs | ev-battery-testing | EV Battery Testing | embedding | 0.86 | correct accept |
| working safely with high voltage | hv-safety | High-Voltage Safety | embedding | 0.79 | correct review |
| wiring of homes | domestic-wiring | Domestic Wiring | embedding | 0.90 | correct accept |
| repairing solar inverters | solar-inverter-maintenance | Solar Inverter Maintenance | embedding | 0.79 | correct review |
| rewinding electric motors | motor-rewinding | Motor Rewinding | embedding | 0.83 | correct review |
| explaining faults to customers | customer-communication | - | none | 0.57 | **missed** |
| इलेक्ट्रिक वाहन की खराबी जांचना | ev-diagnostics | EV Diagnostics | embedding | 0.68 | correct review |
| घर की वायरिंग | domestic-wiring | Domestic Wiring | embedding | 0.64 | correct review |
| सौर पॅनेल बसवणे | rooftop-solar-installation | Rooftop Solar PV Installation | embedding | 0.94 | correct accept |
| Accounting | (none) | - | none | 0.50 | rejected |
| Tally ERP bookkeeping | (none) | - | none | 0.43 | rejected |
| Cooking | (none) | - | none | 0.56 | rejected |
| Hairdressing | (none) | - | none | 0.51 | rejected |
| Java programming | (none) | PLC Programming | embedding | 0.60 | **false review** |
| Truck driving | (none) | - | none | 0.49 | rejected |
| Graphic design | (none) | - | none | 0.50 | rejected |
| Nursing care | (none) | - | none | 0.50 | rejected |
| Plumbing | (none) | - | none | 0.56 | rejected |
| Tailoring | (none) | - | none | 0.53 | rejected |

For "rejected" rows, the confidence shown is the best candidate's, which was too low to assign.

## 6. Known limitations

1. **Tiny, synthetic test set** (44 phrases, 17 skills). With the real 150–300-skill vocabulary,
   unrelated phrases will find closer neighbours, so expect **more review items** and
   possibly wrong top candidates. Re-run the evaluation on real data before trusting the numbers.
2. **Thresholds were tuned on the same small set** they are measured on (a risk of overfitting).
3. **Near-domain confusions:** "Java programming" → PLC Programming (review, 0.60). Both are
   "programming"; embeddings cannot tell the domain difference well.
4. **Soft skills with different wording** ("explaining faults to customers" → Customer
   Communication) can be missed. The cheapest fix is **adding aliases**.
5. **Cross-language matches work but with lower confidence** (Hindi phrases went to review at
   0.64–0.68). Three examples are not proof of general Hindi/Marathi quality.
6. **Abbreviations and jargon** ("LOTO", brand names) only work if added as aliases.
7. **First use is slow on Windows:** importing the libraries plus loading the model took ~40 s
   on the dev laptop (encoding itself: ~0.2 s for 44 phrases in one batch). The model is
   loaded once per process and uses ~0.5–1 GB of RAM.
8. **The LLM fallback is only a hook**. No LLM client exists yet (docs/04-architecture.md §4.6).

## 7. How to use it

From `backend/` with the venv active:

```powershell
pip install -r requirements-embeddings.lock.txt      # once: PyTorch (CPU) etc., ~1 GB
pip install -e ".[embeddings]" --no-deps
python -m app.cli.download_embedding_model           # once: ~0.5 GB into models/ (git-ignored)
python -m app.cli.embed_skills                       # after loading skills into the database
python -m app.cli.match_skill "EV troubleshooting" "house wiring"
python -m app.cli.eval_skill_matching                # re-measure (scratch DB, nothing kept)
python -m app.cli.eval_skill_matching --no-embeddings
python -m app.cli.eval_skill_matching --model-dir models/<other> --model <hf-id> --query-prefix "" --document-prefix "" --floor 0.3
```

The model is **never downloaded at runtime**: the app loads it from `models/` only. Re-running
the download command does nothing if the files are already there.

**Tuning knobs** (all in `config/`):

| Want to… | Change |
|---|---|
| Accept fewer matches automatically | raise `scoring.yaml → skill_matching.auto_accept_confidence` |
| Send fewer weak matches to review | raise `skill_matching.min_confidence` or `llm.yaml → embeddings.similarity_floor` |
| Be stricter/looser with spelling | `skill_matching.fuzzy.min_score` |
| Try another model | `llm.yaml → embeddings.model_name`, `local_path`, prefixes, `similarity_floor`; then download, `embed_skills --all`, evaluate |

## 8. Next steps

1. Load the real skill vocabulary and aliases; add aliases for known misses.
2. Build the 150-posting gold set (docs/DATA_COLLECTION_PLAN.md §8.2) and evaluate phrase
   extraction + matching together.
3. Re-calibrate `similarity_floor` and the thresholds on that real data.
4. Connect "review" results to the `review_item` queue (admin screen SCR-15).
