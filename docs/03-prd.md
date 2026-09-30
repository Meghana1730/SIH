# KaushalSetu — MVP Product Requirements Document (PRD)

| | |
|---|---|
| **File** | `docs/03-prd.md` |
| **Audience** | The whole team (6), mentors |
| **Status** | Draft v0.1, for team review |
| **Related** | [`01-domain.md`](01-domain.md) (terms), [`DATA_SOURCE_INVENTORY.md`](DATA_SOURCE_INVENTORY.md) (what data exists), [`DATA_COLLECTION_PLAN.md`](DATA_COLLECTION_PLAN.md) (how we collect it) |
| **Sector / geography** | Electrical + EV + Solar PV · Pune, Nashik, Nagpur, Kolhapur (Maharashtra) |
| **Languages** | English, Hindi, Marathi |

> **Numbers, names and events in this document are illustrative.** Institutes ("Example ITI A"), employers ("Example EV Services") and the Nashik EV event are fictional or synthetic. No government statistic or official identifier is stated here.

---

## Contents
1. [Product objective](#1-product-objective)
2. [The one rule of this MVP: the golden path](#2-the-one-rule-of-this-mvp-the-golden-path)
3. [User personas and their problems](#3-user-personas-and-their-problems)
4. [MVP scope, nice-to-have scope, non-goals](#4-mvp-scope-nice-to-have-scope-non-goals)
5. [User stories](#5-user-stories)
6. [Functional requirements](#6-functional-requirements)
7. [Scoring and logic definitions](#7-scoring-and-logic-definitions)
8. [Screens](#8-screens)
9. [User flows](#9-user-flows)
10. [Data requirements](#10-data-requirements)
11. [AI requirements](#11-ai-requirements)
12. [API requirements (high level)](#12-api-requirements-high-level)
13. [Non-functional requirements](#13-non-functional-requirements)
14. [Security and privacy requirements](#14-security-and-privacy-requirements)
15. [Explainability requirements](#15-explainability-requirements)
16. [Synthetic-data rules](#16-synthetic-data-rules)
17. [Demo requirements](#17-demo-requirements)
18. [Acceptance criteria](#18-acceptance-criteria)
19. [Delivery plan, cut list, risks](#19-delivery-plan-cut-list-risks)

---

## 1. Product objective

### Problem (one paragraph)
Skill courses in India's ITIs, PMKVY centres and polytechnics can drift away from changing local industry demand. Employers struggle to find job-ready candidates, trainees finish courses with weak placement, and planners lack timely, local, evidence-based signals. The root causes are in `01-domain.md` §1.

### Objective
> **Show, end to end, that a continuous evidence loop can turn a change in local industry demand into a validated curriculum update, a district action plan and better candidate guidance, within one planning cycle instead of years.**

### What the MVP must prove to judges
| # | Claim | How the MVP proves it |
|---|---|---|
| 1 | Jobs and courses can be compared in one language (skills) | Postings and syllabi are both decomposed into skills, and coverage is computed |
| 2 | Local demand shifts can be detected early | EV skills show as **emerging** in Nashik; a simulated event raises the forecast |
| 3 | The system produces **specific, actionable, evidence-backed** changes | A curriculum diff with evidence, plus equipment and trainer needs |
| 4 | Industry stays in the loop | Employers validate and pledge apprenticeships |
| 5 | Officials get something they already need | A one-click district action-plan PDF |
| 6 | Candidates benefit | Local course guidance with career paths, in Marathi, Hindi or English |
| 7 | It is honest and trustworthy | Every score shows its breakdown, evidence, confidence and a synthetic-data badge |

### Prototype success measures (what we measure in the demo)
| Measure | Target |
|---|---|
| Golden-path demo completes without errors | 3 rehearsals in a row |
| Planted synthetic patterns rediscovered by the engines (§16) | 6 of 6 |
| Skill extraction quality on the 150-posting gold set | Precision ≥ 0.75, recall ≥ 0.60 (stretch: 0.80 / 0.70) |
| Recommendations with at least 2 evidence items | 100% of those shown in the demo |
| Time from "Simulate event" click to updated dashboards | ≤ 60 seconds |

We do **not** claim real-world impact numbers. Real-world impact metrics (placement rate change, mismatch reduction) are described as what a pilot *would* measure.

---

## 2. The one rule of this MVP: the golden path

> **Build one convincing end-to-end vertical slice before anything else.** A feature that is not on the golden path is P1 or later, no matter how interesting it is.

### The golden path (primary demo story)

| Step | What happens | Who sees it | Feature(s) |
|---|---|---|---|
| 1 | An EV industry event in Nashik is simulated ("EV component plant announced, ~1,200 expected jobs", **synthetic**) | Admin | Event simulation |
| 2 | Demand for EV-related roles in Nashik increases (current signals plus forecast uplift) | State / district officer | Demand, forecasting |
| 3 | EV skills (e.g. EV charger installation, high-voltage safety, battery testing) are flagged **emerging** | District officer | Skill trends |
| 4 | Nashik shows an **undersupply** mismatch for EV roles | State / district officer | Supply, mismatch |
| 5 | The Electrician course at *Example ITI A, Nashik* has poor coverage of these skills, so its health score is flagged **OUTDATED** | Institute admin | Course health |
| 6 | A curriculum update is recommended (add a module, update a module), with equipment and trainer needs and evidence | Institute admin / district officer | Curriculum alignment, resource planning, recommendations |
| 7 | Local employers review and **approve** the change | Employer | Employer validation |
| 8 | Employers **pledge apprenticeships** | Employer | Pledges |
| 9 | The district officer generates the **Nashik action-plan PDF** | District officer | Plan PDF |
| 10 | A candidate in Nashik asks (in Marathi) "which course should I do?" and is guided to the updated course, with a career path | Candidate | Candidate + career guidance |

**Slice boundaries:** the engines run generically for all 4 districts and all sector roles. The UI, however, must be **polished only for the golden path**: Nashik, the EV/solar roles, and Example ITI A's Electrician course. The other districts must display correctly but need no special polish.

---

## 3. User personas and their problems

Personas are fictional composites. In the MVP, every persona is a **demo account**.

| ID | Persona | Context | Main goal | Top problems today | MVP depth |
|---|---|---|---|---|---|
| P-SO | **State officer** | State-level skill department official overseeing many districts | Decide where to focus attention and funds across districts | Cannot compare districts on current, local demand; reports are slow and inconsistent | Read-only overview + drill-down |
| P-DO | **District officer** | Member of a District Skill Committee | Produce a credible district plan: which courses to expand, change or reduce | Plans are built from old or broad data; little employer input; manual report writing | **Full (golden path)** |
| P-IA | **Institute administrator** | Principal or head of an ITI / PMKVY training centre | Keep courses relevant; improve placement | Doesn't know which modules are outdated; equipment and trainer needs discovered too late | **Full (golden path)** |
| P-SSC | **SSC reviewer** | Curriculum expert at a Sector Skill Council | Update standards (QPs/NOS) using evidence | Evidence arrives anecdotally and slowly; hard to see cross-district patterns | Minimal (P1) |
| P-EM | **Employer** | Small solar installer, EV service centre, or manufacturer HR | Hire job-ready people; influence training | Nobody asks them; freshers lack key skills; no easy way to give input | **Full (golden path)** |
| P-CA | **Candidate** | 12th-pass or ITI-level youth; may prefer Marathi or Hindi; uses a basic phone | Choose a course that leads to a local job | No local outcome data; confusing course names; guidance only in English | **Full (golden path)** |
| P-AD | **Admin** | Our team operating the platform | Keep data healthy; run the demo reliably | Messy data, unmapped skills, demo fragility | **Full (supporting)** |

### Problem → product response
| Problem | Product response (feature) |
|---|---|
| Different vocabularies for jobs and courses | Skill normalisation, coverage (F2, F9) |
| Demand changes faster than curricula | Trends, forecast, event simulation (F6, F7, F19) |
| Invisible MSME demand | Multilingual employer survey (F12) |
| No feedback from outcomes | Placement data drives course health (F8); feedback view (P1) |
| Resources planned separately | Resource planning (F10) |
| Low trust in numbers | Evidence, confidence, breakdowns (F11, §15) |
| Candidates choose blindly | Course and career guidance (F15, F16) |

---

## 4. MVP scope, nice-to-have scope, non-goals

### 4.1 Feature depth table
**P0** = required for the MVP (golden path). **P1** = nice-to-have, build only if all P0 acceptance criteria pass. **Out** = not in this hackathon.

| # | Feature | P0: MVP depth | P1: nice-to-have | Out |
|---|---|---|---|---|
| F1 | Data ingestion & provenance | Load curated + synthetic CSVs via a one-command "load demo data"; provenance fields on every row; ingestion run log | CSV upload from the admin UI; assisted syllabus PDF parsing | Live connectors; scraping |
| F2 | Skill normalisation | Alias dictionary + fuzzy text matching; low-confidence matches go to a review queue | Embedding similarity; LLM-assisted extraction | Automatic new-skill creation without review |
| F3 | Demand analysis | Demand index + estimated openings per role and skill × district × quarter, with components | More signal types | Real-time demand |
| F4 | Supply analysis | Annual trained output per role × district from course offerings | Migration between districts | — |
| F5 | Mismatch | Supply ÷ demand ratio and status; state map + district table | Skill-level mismatch heatmap | — |
| F6 | Emerging / declining skills | Rule-based trend status over 4–6 quarters | External trend signals | — |
| F7 | Basic forecasting | Linear trend + event uplift, 6-quarter horizon, with a simple range | Statistical models (e.g. exponential smoothing) with backtest | ML forecasting |
| F8 | Course health | 0–100 score with breakdown and flags | Trend of health over time | — |
| F9 | Curriculum alignment | Curriculum diff (ADD / UPDATE / DEMOTE) with a template-based module outline | LLM-polished module wording, linked to NOS | Auto-publishing curricula |
| F10 | Resource planning | Equipment gaps + trainer upskilling (ToT) needs from mappings | Indicative cost totals (labelled estimates); seat-change suggestions with costs | Procurement workflows |
| F11 | Evidence-backed recommendations | Recommendation list + detail with evidence, confidence, priority and status | Priority tuning UI | — |
| F12 | Employer survey | Web form in English, Hindi and Marathi (< 2 minutes) | Telegram bot version | WhatsApp, IVR / voice |
| F13 | Employer validation | Approve / Reject / Not needed + comment on each recommendation | Validation reminders | — |
| F14 | Apprenticeship pledges | Pledge a count + timeframe on a recommendation; totals shown in the plan | Pledge follow-up tracking | Legal agreements |
| F15 | Candidate course guidance | 3-question wizard → top 3 courses with local outcomes and "why", in 3 languages, mobile-friendly | Free-text chat assistant | Accounts for candidates |
| F16 | Career-path guidance | Next 1–2 roles from a role ladder, with the skills to learn | Multi-step path search | — |
| F17 | District action-plan PDF | English PDF generated in one click | Marathi / Hindi PDF | Official format certification |
| F18 | Admin / data quality | Data-quality summary; review queue; load / reset demo | Config (weights) editor with versioning | — |
| F19 | Synthetic event simulation | Form to add a synthetic event → pipeline re-runs → screens update | Multiple event types (closure, policy) | — |
| — | SSC reviewer screen | — | Minimal: list of module drafts + approve / reject | Full QP-revision workflow |
| — | Feedback loop view | Course health already uses (synthetic) placement outcomes | "Predicted vs actual" view; admin-approved weight changes | Automatic weight changes |

### 4.2 Explicit non-goals
1. **No real integration with government systems** (NCS, SIDH, DVET, NQR). We design API contracts only.
2. **No live scraping** of any website.
3. **No real candidate, trainer or placement personal data.**
4. **No approval authority.** The product proposes; officials, SSCs and boards decide. Nothing is auto-published as official curriculum.
5. **No claims of real-world accuracy or impact** from synthetic results.
6. **No other sectors or states** beyond Electrical / EV / Solar PV in the 4 districts.
7. **No native mobile app, SMS, WhatsApp or IVR** in the MVP.
8. **No assessments, certification, LMS content, payments or job applications.**
9. **No candidate accounts or logins.** Candidate guidance is anonymous.
10. **No production-scale performance, high availability or multi-tenant hosting.**

---

## 5. User stories

Format: *As a [persona], I want [capability] so that [benefit].* **Pri** = P0/P1.

### State officer
| ID | Story | Pri | Features |
|---|---|---|---|
| US-01 | As a state officer, I want a map of the 4 districts coloured by mismatch so that I can see where attention is needed. | P0 | F5 |
| US-02 | As a state officer, I want to compare districts on top shortages and surpluses so that I can prioritise support. | P0 | F3–F5 |
| US-03 | As a state officer, I want to open any district's dashboard so that I can see the detail behind the colour. | P0 | F3–F7 |

### District officer
| ID | Story | Pri | Features |
|---|---|---|---|
| US-04 | As a district officer, I want to see roles and skills ranked by shortage and trend in my district so that I know what is changing. | P0 | F3–F6 |
| US-05 | As a district officer, I want a forecast for key roles that reflects announced industry events so that I can plan ahead. | P0 | F7, F19 |
| US-06 | As a district officer, I want a list of recommendations with evidence and employer validation status so that I can decide what to include in the plan. | P0 | F11, F13 |
| US-07 | As a district officer, I want to generate a district action-plan PDF in one click so that I don't have to write the report by hand. | P0 | F17 |
| US-08 | As a district officer, I want to see total apprenticeship pledges per recommendation so that I can show industry commitment. | P0 | F14, F17 |

### Institute administrator
| ID | Story | Pri | Features |
|---|---|---|---|
| US-09 | As an institute admin, I want a health score for each of my courses with a breakdown so that I understand what is weak. | P0 | F8 |
| US-10 | As an institute admin, I want a side-by-side curriculum diff (current vs recommended) with evidence so that I know exactly what to change and why. | P0 | F9, F11 |
| US-11 | As an institute admin, I want the equipment and trainer upskilling needed for each change so that I can plan resources. | P0 | F10 |
| US-12 | As an institute admin, I want to mark a recommendation as "planned" or "implemented" so that the district officer sees progress. | P1 | F11 |

### SSC reviewer
| ID | Story | Pri | Features |
|---|---|---|---|
| US-13 | As an SSC reviewer, I want to see emerging and declining skills across districts so that I can consider revising standards. | P1 | F6 |
| US-14 | As an SSC reviewer, I want to approve or reject draft module outlines so that official alignment stays with experts. | P1 | F9 |

### Employer
| ID | Story | Pri | Features |
|---|---|---|---|
| US-15 | As an employer, I want to tell the platform my hiring needs in under 2 minutes in Marathi, Hindi or English so that my demand is counted. | P0 | F12 |
| US-16 | As an employer, I want to review proposed course changes near me and approve or reject them so that training matches real work. | P0 | F13 |
| US-17 | As an employer, I want to pledge apprenticeships for an approved change so that my commitment is recorded. | P0 | F14 |
| US-18 | As an employer, I want to see which of my inputs were used so that I trust the process. | P1 | F11 |

### Candidate
| ID | Story | Pri | Features |
|---|---|---|---|
| US-19 | As a candidate, I want to answer 3 simple questions in my language and get the top 3 courses near me so that I can choose well. | P0 | F15 |
| US-20 | As a candidate, I want to see local placement rate, salary range and why a course is recommended so that I can trust the advice. | P0 | F15 |
| US-21 | As a candidate, I want to see what job I could grow into next and what to learn so that I can plan my career. | P0 | F16 |
| US-22 | As a candidate, I want to ask questions in free text so that I can get help without a form. | P1 | F15 |

### Admin
| ID | Story | Pri | Features |
|---|---|---|---|
| US-23 | As an admin, I want to load or reset all demo data with one action so that the demo is reliable. | P0 | F1, F18 |
| US-24 | As an admin, I want to see data-quality checks so that I can catch problems before the demo. | P0 | F18 |
| US-25 | As an admin, I want to review low-confidence skill matches so that normalisation stays accurate. | P0 | F2, F18 |
| US-26 | As an admin, I want to simulate an industry event so that I can show the system reacting. | P0 | F19 |
| US-27 | As an admin, I want to change scoring weights with a version history so that tuning is controlled. | P1 | F18 |

---

## 6. Functional requirements

IDs are grouped by feature. "Shall" = required for the stated priority.

### F1: Data ingestion & provenance (P0)
| ID | Requirement |
|---|---|
| FR-1.1 | The system shall load all reference, curated and synthetic CSV files listed in §10 with a single command or admin action ("Load demo data"). |
| FR-1.2 | Every loaded record shall carry the provenance fields `source_id`, `source_ref`, `fetched_at`, `license_note`, `is_synthetic`. |
| FR-1.3 | Each load shall create an **ingestion run** record: source, start and end time, rows loaded, rows rejected, and error messages. |
| FR-1.4 | Rows failing validation (missing required fields, unknown district code, unknown skill ID) shall be rejected and listed. They must not be silently dropped. |
| FR-1.5 | Loading shall be **idempotent**: running it twice produces the same database state, with no duplicates. |
| FR-1.6 | Job-posting text shall be deduplicated (same normalised title, employer, district and posting week). |
| FR-1.7 | Place names in postings and surveys shall be mapped to a district through the alias table. Unmapped places go to the review queue. |

### F2: Skill normalisation (P0)
| ID | Requirement |
|---|---|
| FR-2.1 | The system shall extract skill mentions from posting text, survey answers and syllabus modules using (a) exact alias matching and (b) fuzzy matching. |
| FR-2.2 | Each extracted skill shall have a confidence value (0–1) and a method label (`ALIAS`, `FUZZY`, `EMBEDDING`, `LLM`, `HUMAN`). |
| FR-2.3 | Matches below the auto-accept threshold (default 0.85) shall go to the **review queue**. Matches below the minimum threshold (default 0.60) are discarded but logged. |
| FR-2.4 | Aliases shall support English, Hindi and Marathi text. |
| FR-2.5 | The system shall assign a proficiency band (1–4) using simple rules: experience years, and keywords such as helper, technician, senior, supervisor. Default is band 2 when there is no signal. |
| FR-2.6 | An evaluation command shall report precision, recall and F1 against the gold set. |

### F3: Demand analysis (P0)
| ID | Requirement |
|---|---|
| FR-3.1 | For each role × district × quarter, compute the **demand index (0–100)** and its components (§7.1). |
| FR-3.2 | For each role × district, compute **estimated annual openings** (§7.2), labelled as an estimate with its assumptions. |
| FR-3.3 | For each skill × district × quarter, compute skill mention counts and share. |
| FR-3.4 | Each demand value shall store a **confidence** level (High / Medium / Low) (§7.9). |

### F4: Supply analysis (P0)
| ID | Requirement |
|---|---|
| FR-4.1 | For each role × district, compute **annual trained output** from the course offerings mapped to that role (§7.3). |
| FR-4.2 | The supply calculation shall show which course offerings contributed. |

### F5: Mismatch (P0)
| ID | Requirement |
|---|---|
| FR-5.1 | Compute the supply ÷ openings **ratio** and **status** (UNDERSUPPLIED / BALANCED / OVERSUPPLIED) per role × district (§7.4). |
| FR-5.2 | Compute a **district mismatch score** for the state map (§7.4). |
| FR-5.3 | The state view shall show all 4 districts, coloured by mismatch score, with a legend. |

### F6: Emerging and declining skills (P0)
| ID | Requirement |
|---|---|
| FR-6.1 | Classify each skill × district as EMERGING, STABLE or DECLINING using the rules in §7.5. |
| FR-6.2 | Show a small trend chart (mentions per quarter) for any skill. |

### F7: Basic forecasting (P0)
| ID | Requirement |
|---|---|
| FR-7.1 | Forecast the demand index and openings per role × district for the next 6 quarters (§7.6). |
| FR-7.2 | Include uplift from sector events (real or synthetic) using the lag and realisation assumptions in configuration. |
| FR-7.3 | Show the forecast as a line with a shaded range, clearly labelled "indicative forecast". |

### F8: Course health (P0)
| ID | Requirement |
|---|---|
| FR-8.1 | Compute a **course health score (0–100)** per course offering with a component breakdown (§7.7). |
| FR-8.2 | Assign flags: `OUTDATED`, `AT_RISK`, `LOW_PLACEMENT`, `OVERSUPPLIED`, `UNDERSUPPLIED` (§7.7). |
| FR-8.3 | Show skill **coverage** for each role the course maps to, listing covered, partially covered and missing skills. |

### F9: Curriculum alignment (P0)
| ID | Requirement |
|---|---|
| FR-9.1 | Generate a **curriculum diff** per course offering with change types ADD_MODULE, UPDATE_MODULE and DEMOTE_MODULE (§7.8). |
| FR-9.2 | Each ADD_MODULE shall include a **draft module outline**: title, target skills with bands, suggested hours (range), practical activities, and required equipment. It is generated from templates in P0. |
| FR-9.3 | Every draft shall be labelled **"Draft — requires approval by the competent authority"**. |
| FR-9.4 | The UI shall show current modules and recommended changes side by side. |
| FR-9.5 | Each change shall indicate **who decides** (e.g. DGT process for ITI trades, the owning SSC for QP-based courses, the institute for add-on courses), using the routing table in `01-domain.md` §11. |

### F10: Resource planning (P0)
| ID | Requirement |
|---|---|
| FR-10.1 | For each recommended skill change, list the **required equipment** (from the skill → equipment mapping) minus what the institute already has. |
| FR-10.2 | List **trainer upskilling (ToT) needs**: required skills and bands that no current trainer at the institute covers. |
| FR-10.3 | (P1) Show indicative cost totals, labelled "estimate". |

### F11: Evidence-backed recommendations (P0)
| ID | Requirement |
|---|---|
| FR-11.1 | Recommendations shall be generated for course changes (F9), seat changes (EXPAND_SEATS / REDUCE_SEATS from F5), trainer needs and equipment needs (F10). |
| FR-11.2 | Each recommendation shall have: type, target, district, **evidence list**, **confidence**, **priority** (High / Medium / Low), **status**, decision owner, and `is_synthetic` if it was derived from synthetic data. |
| FR-11.3 | Status lifecycle: `DRAFT → UNDER_VALIDATION → VALIDATED → IN_PLAN` (P1: `IMPLEMENTED`), plus `REJECTED`. Every status change is recorded in the audit log. |
| FR-11.4 | A recommendation moves to `VALIDATED` when at least N employers approve (default N = 3) and approvals exceed rejections. |
| FR-11.5 | The district officer can add `VALIDATED` recommendations to the district plan (`IN_PLAN`). |

### F12: Employer survey (P0)
| ID | Requirement |
|---|---|
| FR-12.1 | A public web form (no login) in English, Hindi and Marathi, completable in under 2 minutes. |
| FR-12.2 | The form starts with the **consent statement**. There is no submission without consent. |
| FR-12.3 | Fields: business type, size (self-reported), district, roles needed with counts and timeframe, hardest skills (pick from a list + free text), level needed, apprenticeship willingness, re-contact consent. |
| FR-12.4 | Free-text skills are normalised through F2. |
| FR-12.5 | Submissions immediately contribute to the survey component of demand at the next pipeline run. In the demo, that run can be triggered manually. |
| FR-12.6 | Spam protection: basic rate limiting, and required fields validated. |

### F13: Employer validation (P0)
| ID | Requirement |
|---|---|
| FR-13.1 | Logged-in employers see recommendations for their district, as cards showing the change, the evidence summary and the decision owner. |
| FR-13.2 | The employer can choose **Approve**, **Reject** or **Not needed**, and add an optional comment. One vote per employer per recommendation; it can be changed. |
| FR-13.3 | Vote counts and comments are shown on the recommendation detail and in the plan. |

### F14: Apprenticeship pledges (P0)
| ID | Requirement |
|---|---|
| FR-14.1 | On an approved recommendation, an employer can pledge a **number** of apprentices or hires and a **timeframe** (in months). |
| FR-14.2 | Pledges are summed per recommendation and per district, and shown in the plan. |
| FR-14.3 | Pledges are labelled "non-binding intent". |

### F15: Candidate course guidance (P0)
| ID | Requirement |
|---|---|
| FR-15.1 | A mobile-friendly wizard in English, Hindi and Marathi, with 3 questions: district, education level, interest area (Electrical / Solar / EV / Not sure). No login and no personal data collected. |
| FR-15.2 | Output: the **top 3 course offerings** near the candidate, ranked by §7.10. Each shows local placement rate, salary range, demand trend, and a **"why this course"** explanation. |
| FR-15.3 | Every number shows a confidence label and, where applicable, a **"demo data"** badge. |
| FR-15.4 | The guidance never promises a job. It shows the text: "This is guidance, not a guarantee." |

### F16: Career-path guidance (P0)
| ID | Requirement |
|---|---|
| FR-16.1 | For a recommended course, show the **entry role** and the **next 1–2 roles** from the role ladder, with the skills to learn for each step. |
| FR-16.2 | The role ladder is curated data (§10). It is not generated by AI at runtime. |

### F17: District action-plan PDF (P0)
| ID | Requirement |
|---|---|
| FR-17.1 | One click generates a PDF for the selected district and quarter. |
| FR-17.2 | Required sections: cover (district, period, date, data disclosure); summary (top 5 shortages and surpluses); mismatch table; emerging and declining skills; course actions; curriculum changes with validation status and pledges; trainer and equipment needs; candidate guidance summary; evidence appendix; data confidence and synthetic-data disclosure. |
| FR-17.3 | Only recommendations with status `IN_PLAN` appear under "actions". `VALIDATED` ones not yet added appear under "under consideration". |
| FR-17.4 | The PDF footer states: "Draft generated by KaushalSetu — for discussion; not an official document." |
| FR-17.5 | (P1) Marathi and Hindi versions. |

### F18: Admin and data quality (P0)
| ID | Requirement |
|---|---|
| FR-18.1 | **Load demo data** and **Reset demo** actions. Reset restores the exact pre-demo state in ≤ 60 seconds. |
| FR-18.2 | **Run pipeline** action: recomputes demand, supply, mismatch, trends, forecast, health and recommendations. |
| FR-18.3 | **Data-quality summary**: row counts per file, rejected rows, unmapped places, unmapped skills (%), duplicate rate, synthetic vs real counts. |
| FR-18.4 | **Review queue**: accept, reject or remap low-confidence skill and place matches. |
| FR-18.5 | (P1) **Config editor** for weights and thresholds, with version history and an audit entry for every change. |

### F19: Synthetic event simulation (P0)
| ID | Requirement |
|---|---|
| FR-19.1 | Admin form fields: district, sector, event type (P0: `NEW_PLANT`), expected jobs, announcement quarter. |
| FR-19.2 | The created event is stored with `is_synthetic = true` and labelled "Simulated event" everywhere it appears. |
| FR-19.3 | Creating an event triggers a pipeline re-run. Forecasts, recommendations priority and dashboards update within **60 seconds**. |
| FR-19.4 | Simulated events can be deleted. Reset removes them all. |

### Cross-cutting (P0)
| ID | Requirement |
|---|---|
| FR-X.1 | **Authentication:** demo accounts for each role. A **demo-mode role switcher** is visible only when demo mode is enabled. |
| FR-X.2 | **Authorisation:** each role sees only its permitted screens and data (§14). |
| FR-X.3 | **Language switcher** on the candidate and employer screens (English / हिन्दी / मराठी). Officer, institute and admin screens are English-only in P0. |
| FR-X.4 | A public **"About the data"** page listing real vs synthetic sources, attributions and the calculation methods. |
| FR-X.5 | All weights, thresholds and assumptions are read from a configuration file, not hard-coded. |

---

## 7. Scoring and logic definitions

**Keep it simple and explainable.** All numbers below are **default configuration values** (our assumptions), editable in config. They are not official standards.

**Notation:** role *r*, skill *s*, district *d*, quarter *q* (e.g. `2026Q3`).

### 7.1 Demand index (0–100)
| Component | Weight | Definition |
|---|---|---|
| Postings signal **P** | 0.5 | Deduplicated postings for *r* in *d* during *q*, scaled 0–100 across roles in the same district and quarter (min-max) |
| Survey signal **S** | 0.3 | Survey-reported headcount for *r* in *d* (latest response per employer, last 12 months), scaled 0–100 |
| Event signal **E** | 0.2 | Expected jobs for *r* from sector events whose lag window includes *q*, scaled 0–100 |

`Demand index = 0.5·P + 0.3·S + 0.2·E`. If a component has no data, re-weight the others and lower the confidence.

### 7.2 Estimated annual openings
`Openings(r,d) = postings in the last 4 quarters ÷ coverage_factor`. The default `coverage_factor = 0.3` is **an assumption** that only a fraction of openings are posted online. It is displayed on screen as an assumption. Survey headcount is shown alongside as corroboration.

### 7.3 Annual trained output (supply)
`Supply(r,d) = Σ over course offerings in d mapped to r of (seats filled × completion rate)`. The default completion rate is 0.8 when unknown (an assumption).

### 7.4 Mismatch
- `Ratio = Supply ÷ Openings`
- Status: **UNDERSUPPLIED** if the ratio is < 0.7; **BALANCED** from 0.7 to 1.5; **OVERSUPPLIED** if > 1.5
- **District mismatch score** (for the map) = the average of |ratio − 1| across the district's roles, weighted by openings, capped and scaled to 0–100.

### 7.5 Skill trend
- **EMERGING:** mentions grew by ≥ 25% comparing the last 2 quarters with the 2 before them, AND there are ≥ 20 mentions in the last 2 quarters.
- **DECLINING:** mentions fell in 3 consecutive quarters, AND fell by ≥ 20% in total.
- Otherwise **STABLE**.

### 7.6 Basic forecast
- **Baseline:** a straight-line trend fitted to the last 6 quarters of openings (or the demand index), extended 6 quarters ahead.
- **Event uplift:** `expected jobs × realisation factor (default 0.6) × role share (from the staffing-pattern assumptions)`, spread evenly over quarters +2 to +5 after the announcement (default lag window).
- **Range:** ± 20% of the forecast value (a simple, clearly labelled band).
- Always labelled **"indicative"**.

### 7.7 Course health (0–100)
| Component | Weight | Definition |
|---|---|---|
| Placement rate | 30 | Placed ÷ completed, last 2 cohorts |
| Skill coverage | 30 | See below |
| Demand trend | 20 | Growth of the demand index for the course's mapped roles, scaled 0–1 |
| Retention | 10 | Still employed at 6 months ÷ placed |
| Wage | 10 | Median placed salary ÷ district median for the role, capped at 1 |

**Coverage** = Σ over the role's skills of (importance × covered) ÷ Σ importance. `covered` is 1 if the skill is taught at ≥ the required band, 0.5 if at a lower band, and 0 otherwise. Skill importance comes from `role_skill` and is boosted ×1.5 for EMERGING skills in the district. A course that maps to several roles (`course_role`) shows the coverage for each role (FR-8.3); its own coverage (for the score and the OUTDATED flag) is computed over the **union** of those roles' skills, each skill at its highest importance.

**Oversupply penalty:** if the ratio is > 1.5, subtract up to 20 points (linearly up to a ratio of 3.0).

**Flags:**
| Flag | Condition |
|---|---|
| `OUTDATED` | coverage < 0.5 |
| `AT_RISK` | score < 50 |
| `LOW_PLACEMENT` | placement rate < 40% |
| `OVERSUPPLIED` / `UNDERSUPPLIED` | from §7.4 |

### 7.8 Curriculum diff rules
| Change | Rule |
|---|---|
| ADD_MODULE | A skill with importance ≥ 0.5 for a mapped role, EMERGING or high demand in the district, and coverage 0 in the course |
| UPDATE_MODULE | A skill that is taught, but at a band below the required band |
| DEMOTE_MODULE | ≥ 70% of a module's skill weight is DECLINING. It is shown as a **candidate** until ≥ 3 employers vote "Not needed" or approve the demotion. |
| EXPAND_SEATS / REDUCE_SEATS | From the mismatch status for the course's main role |

### 7.9 Confidence (High / Medium / Low)
| Level | Condition |
|---|---|
| High | ≥ 3 independent source types (postings, surveys, events, consultations, outcomes) AND ≥ 30 underlying records |
| Medium | 2 source types, OR ≥ 10 records |
| Low | Otherwise. The UI must show a caution. |

### 7.10 Candidate course ranking
`Rank score = 0.4 × local placement rate + 0.3 × demand trend of the course's roles + 0.2 × interest match + 0.1 × proximity (same district = 1, another district = 0.5)`. Ties are broken by the course health score.

### 7.11 Recommendation priority
| Priority | Condition |
|---|---|
| High | Undersupplied role, or an OUTDATED course, AND confidence ≥ Medium |
| Medium | Other ADD / UPDATE changes, or Low confidence |
| Low | DEMOTE candidates, or minor equipment additions |

---

## 8. Screens

**P0 screens must be built. P1 screens only if time allows.**

| ID | Screen | Role(s) | Pri | Key content | Key actions |
|---|---|---|---|---|---|
| SCR-01 | Login + demo role switcher | All (not candidate) | P0 | Demo accounts; "demo mode" banner | Log in; switch role |
| SCR-02 | State overview | State officer | P0 | Map of 4 districts coloured by mismatch; district comparison table; quarter selector | Open a district |
| SCR-03 | District dashboard | State / district officer | P0 | Top shortages and surpluses; demand vs supply chart; emerging and declining skills; forecast chart; active events | Open role / skill; go to recommendations |
| SCR-04 | Role / skill detail | Officers | P0 | Trend chart, forecast with range, evidence list, contributing courses | — |
| SCR-05 | Recommendations inbox + evidence drawer | Officers | P0 | Filterable list (type, status, priority); drawer with evidence, confidence, votes, pledges, decision owner | Add to plan; reject |
| SCR-06 | District plan preview | District officer | P0 | Plan sections preview | **Generate PDF** |
| SCR-07 | My courses | Institute admin | P0 | Course offerings with health gauge and flags | Open a course |
| SCR-08 | Course detail | Institute admin (+ officers read-only) | P0 | Health breakdown; coverage (covered / partial / missing); **curriculum diff side by side**; draft module outline; equipment and ToT needs; evidence | Mark planned (P1) |
| SCR-09 | SSC review | SSC reviewer | P1 | Emerging and declining skills across districts; module drafts | Approve / reject draft |
| SCR-10 | Employer survey (public) | Employer | P0 | Consent; < 2-minute form; language switch | Submit |
| SCR-11 | Employer validation | Employer | P0 | Cards: change, why, evidence summary, current votes | Approve / Reject / Not needed; comment; **Pledge** |
| SCR-12 | Candidate wizard (public, mobile) | Candidate | P0 | 3 questions; language switch | Get guidance |
| SCR-13 | Candidate results + career path | Candidate | P0 | Top 3 courses with placement, salary range, trend, "why", confidence, demo badge; career ladder | Change answers |
| SCR-14 | Admin: data & pipeline | Admin | P0 | Ingestion runs; row counts; **Load / Reset / Run pipeline** | Run actions |
| SCR-15 | Admin: review queue | Admin | P0 | Low-confidence skill and place matches | Accept / reject / remap |
| SCR-16 | Admin: data quality | Admin | P0 | Checks and results (§18 DQ list) | — |
| SCR-17 | Admin: simulate event | Admin | P0 | Event form; list of simulated events | Create / delete event |
| SCR-18 | Admin: configuration | Admin | P1 | Weights, thresholds, assumptions; version history | Save new version |
| SCR-19 | About the data (public) | All | P0 | Real vs synthetic sources, attributions, calculation summary | — |

**UI rules for all screens:**
- Any value derived from synthetic data shows a small **"demo data"** badge.
- Every score is clickable and opens its breakdown.
- Empty, loading and error states are designed. There are no blank screens.
- Candidate and employer screens work at **360 px width** (a small phone).

---

## 9. User flows

### UF-1: Golden path (demo)
```
Admin: SCR-17 simulate "EV plant, Nashik" → pipeline re-runs
 → State officer: SCR-02 Nashik turns red → SCR-03 Nashik dashboard (EV skills EMERGING, forecast jumps)
 → Institute admin: SCR-07 → SCR-08 Electrician @ Example ITI A: health flagged OUTDATED, curriculum diff + equipment/ToT
 → Employer: SCR-11 approve change + pledge apprentices (repeat with 3 demo employers, or pre-seeded votes + 1 live vote)
 → District officer: SCR-05 recommendation now VALIDATED → Add to plan → SCR-06 Generate PDF
 → Candidate: SCR-12 (Marathi) Nashik / 12th pass / EV → SCR-13 updated course ranked top with career path
```

### UF-2: District officer quarterly review
SCR-03 → review top shortages → SCR-05 filter High priority → open the evidence drawer → add validated items to the plan → SCR-06 PDF.

### UF-3: Institute admin reviews a course
SCR-07 → pick the lowest-health course → SCR-08 → read the breakdown → review the diff and resources → (P1) mark as planned.

### UF-4: Employer shares demand
Opens the survey link → picks a language → consents → fills the form (< 2 minutes) → sees a thank-you with "what happens next".

### UF-5: Employer validates and pledges
Login → SCR-11 → reads a card → Approve + comment → Pledge (count, timeframe) → confirmation.

### UF-6: Candidate guidance
SCR-12 (no login) → language → district → education → interest → SCR-13 → expands "why" → views the career path.

### UF-7: Admin data operations
SCR-14 Load demo data → SCR-16 check quality → SCR-15 resolve the review queue → SCR-14 Run pipeline.

### UF-8: Demo reset
SCR-14 **Reset demo** → confirmation → the state is restored in ≤ 60 seconds → the golden path can start again.

---

## 10. Data requirements

Sources and collection are defined in `DATA_SOURCE_INVENTORY.md` and `DATA_COLLECTION_PLAN.md`. This section defines **what the product needs**.

### 10.1 Time frame for demo data
- **History:** 6 quarters, `2025Q2` to `2026Q3`. The current quarter is `2026Q3`.
- **Forecast:** 6 quarters, `2026Q4` to `2028Q1`.

### 10.2 Required datasets (MVP)
| Dataset | Minimum content | Real / synthetic | Required by |
|---|---|---|---|
| Districts | 4 districts with verified official district codes | Real | All |
| Place-name aliases | ≥ 50 names → district | Real (curated) | F1 |
| District map shapes | 4 districts | Real (open license, attributed) | SCR-02 (fallback: points) |
| Sectors | Electrical, EV, Solar PV | Curated | All |
| Job roles | 15–25, with QP / occupation links where verified | Real → curated | F3–F16 |
| Role → skill mapping | 5–15 skills per role, with importance (0–1) and required band | Curated | F8, F9 |
| Role ladder (career steps) | Next-role links for all roles | Curated | F16 |
| Skills + aliases | 150–300 skills; aliases in English, Hindi and Marathi (top 50 at least) | Curated from real NOS and syllabi | F2 |
| QPs / NOS (reference) | 6–12 QPs relevant to the sector | Real (verified on NQR) | F9 (decision routing, alignment) |
| Courses, modules, module → skill | 4–6 courses, including **Electrician** (golden path) | Real syllabi → curated | F8, F9 |
| Equipment, skill → equipment | Equipment for all MVP courses | Real (syllabus annexures) → curated | F10 |
| Institutes (demo) | 8–12 **fictional** institutes across 4 districts, incl. **Example ITI A, Nashik** | Synthetic | F4, F8 |
| Course offerings | Seats, seats filled, completion per institute × course × year | Synthetic (ranges informed by real intake) | F4 |
| Trainers + trainer skills | 2–6 pseudonymous trainers per institute | Synthetic | F10 |
| Institute equipment inventory | Per demo institute | Synthetic | F10 |
| Job postings | ≥ 2,000 synthetic across 4 districts × 6 quarters, plus ≥ 500 real (NLP testing only) | Synthetic + real | F2, F3, F6 |
| Employer survey responses | 60–100 synthetic + any real (anonymised) | Synthetic + real | F3 |
| Sector events | 5–15 real (cited) + the simulated event(s) | Real + synthetic | F7, F19 |
| Enrollments, placements, retention, wages | All demo cohorts | Synthetic | F8, F15 |
| Employers (demo accounts) | ≥ 5 in Nashik, ≥ 2 in each other district | Synthetic | F13, F14 |
| Gold-labelled postings | 150 | Real text, human labels | F2 evaluation |
| Configuration | Weights, thresholds, assumptions (coverage factor, completion rate, realisation factor, lag, staffing pattern) | Assumptions (labelled) | All |

### 10.3 Data rules
1. Provenance fields on every row (FR-1.2).
2. `is_synthetic = true` on all generated rows, with a UI badge (§16).
3. Districts are referenced only by verified code, never by free-text name.
4. No personal data in any dataset (§14).
5. **Seeded, deterministic** synthetic generation: the same seed always gives the same data.

---

## 11. AI requirements

**Principle:** the MVP must **work fully without any paid AI service**. AI features improve quality but are never a single point of failure on stage.

| ID | Capability | P0 approach | P1 enhancement | Guardrails |
|---|---|---|---|---|
| AI-1 | Skill extraction from text | Alias dictionary + fuzzy matching (multilingual aliases) | Sentence embeddings (free, local model) for unmatched phrases; LLM extraction with structured output | Confidence scores; review queue; no auto-created skills |
| AI-2 | Proficiency band inference | Keyword and experience rules | LLM fallback for ambiguous postings | Default band 2; show the method |
| AI-3 | Module outline drafting | Template filled from skill descriptions, NOS text and the equipment list | LLM rewrites the template for readability | Always "Draft — requires approval"; no invented NOS codes; the output must reference only skills and equipment present in our data |
| AI-4 | "Why this course" explanation | Template sentences from the ranking components | LLM paraphrase in Hindi and Marathi | Numbers must come from the database, never from the model |
| AI-5 | Translation of UI and alias text | Human-written strings for the UI; human-checked aliases | Machine translation drafts (e.g. an open-source Indian-language model), **human-checked** | No machine translation shown unreviewed on candidate screens |
| AI-6 | Candidate free-text assistant | — | Answers only from platform data (retrieval), in 3 languages | "I don't know" fallback; no invented numbers; no personal data |

### AI quality requirements
| ID | Requirement |
|---|---|
| AIQ-1 | Skill extraction on the gold set reaches precision ≥ 0.75 and recall ≥ 0.60 (stretch: 0.80 / 0.70), reported by the evaluation command. |
| AIQ-2 | Any LLM call is **cached**, so the same input gives the same output, which keeps demos deterministic. |
| AIQ-3 | A config switch turns off all LLM calls. The product stays fully functional using the P0 approaches. |
| AIQ-4 | No personal data is ever sent to an external AI service. |
| AIQ-5 | Every AI-produced item is labelled with its method (e.g. "matched by alias", "drafted from template"). |

---

## 12. API requirements (high level)

Detailed contracts belong in the architecture document (`docs/04-architecture.md`). Requirements:

- A REST/JSON API with **auto-generated documentation** (OpenAPI).
- **Authentication** for all non-public endpoints. **Role-based authorisation** is enforced on the server, not just hidden in the UI.
- List endpoints support filtering by district, quarter, role and status, and pagination.
- **Every analytic response includes** `confidence`, `is_synthetic` (or a synthetic share), `computed_at`, `config_version`, and, where relevant, `evidence[]` and `components{}`.
- Errors use a consistent structure with a human-readable message.

| Group | Purpose (examples) | Access |
|---|---|---|
| Auth | Log in; current user; demo role switch | All staff roles |
| Reference | Districts, sectors, roles, skills, courses, QPs | Authenticated |
| Analytics | District demand, mismatch, skill trends, forecasts, state summary for the map | Officers, institute (own district), SSC |
| Courses | Institute offerings; course health; curriculum diff; resource needs | Institute (own), officers |
| Recommendations | List, detail, status changes, add to plan | Officers; institute (own, read) |
| Employer | Survey submit (public); validation list; votes; pledges | Public (survey) / employer |
| Candidate | Guidance (district, education, interest) → courses + career path | Public |
| Plans | Generate district plan; download PDF | District / state officer |
| Admin | Load / reset demo; run pipeline; data quality; review queue; simulate events; (P1) config | Admin |
| About | Sources, attributions, method summary | Public |

---

## 13. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Dashboard screens load in ≤ 2 s on a laptop with demo data. The PDF generates in ≤ 15 s. A full pipeline run takes ≤ 60 s. |
| NFR-2 | Reliability | The demo runs **fully offline on one laptop**. A hosted copy is optional. A recorded backup video exists. |
| NFR-3 | Reproducibility | One command builds the environment and loads the demo data from scratch. Synthetic data is seeded and deterministic. |
| NFR-4 | Portability | Setup works on Windows 11 with free tools, documented step by step. |
| NFR-5 | Cost | ₹0. Only free and open-source tools and free tiers. No paid API is required (AIQ-3). |
| NFR-6 | Usability | Candidate and employer flows can be completed without help by a first-time user in ≤ 2 minutes. They use plain language. |
| NFR-7 | Mobile | Candidate and employer screens are usable at 360 px width and on slow connections (light pages, no heavy maps). |
| NFR-8 | Accessibility | Readable contrast; all inputs labelled; keyboard navigable; colour is never the only signal (e.g. status text next to map colour). |
| NFR-9 | Internationalisation | Candidate and employer UI fully available in English, Hindi and Marathi. Devanagari renders correctly in the UI (and in the PDF when P1 is done). |
| NFR-10 | Maintainability | Weights and thresholds live in config; code is organised by feature; README setup steps are kept up to date. |
| NFR-11 | Data integrity | Loading validates references (district, skill, role, course) and rejects bad rows with reasons. |
| NFR-12 | Observability | Ingestion and pipeline runs are logged with counts and errors, visible on SCR-14. |
| NFR-13 | Testability | Each scoring rule in §7 has unit tests on small hand-calculated examples. The golden path has an automated end-to-end check. |

---

## 14. Security and privacy requirements

| ID | Requirement |
|---|---|
| SEC-1 | **No real personal data** of candidates or trainers is stored. Candidates are anonymous; trainers are pseudonymous (T-01…). |
| SEC-2 | The employer survey collects **consent** first and stores no personal phone numbers or names in analytic data. Any real contact list is kept **outside** the app and the repository, and deleted after the hackathon. |
| SEC-3 | Passwords are hashed. Demo accounts use non-reused passwords. Secrets live in environment files that are **not committed**. |
| SEC-4 | **Role-based access control** on every non-public API. Institute admins see only their own institute; employers only their own votes and pledges plus their district's recommendations. |
| SEC-5 | **Audit log** for recommendation status changes, votes, pledges, simulated events, config changes and demo resets. |
| SEC-6 | Public endpoints (survey, candidate guidance) have input validation and basic rate limiting. |
| SEC-7 | No personal data in logs. No personal data is sent to external AI services (AIQ-4). |
| SEC-8 | Hosted deployments (if any) use HTTPS. |
| SEC-9 | Privacy notice on the survey and candidate screens: what is collected, why, and that no personal data is stored. Aligned in spirit with the DPDP Act, 2023. *(The specific obligations are TODO-VERIFY; see `01-domain.md` §19.)* |
| SEC-10 | Attribution and license notes for all real sources on the About page (SCR-19). |

---

## 15. Explainability requirements

| ID | Requirement |
|---|---|
| EXP-1 | **Every score is decomposable.** Demand index, mismatch, course health, coverage and rank score each open a breakdown of their components and weights. |
| EXP-2 | **Every recommendation shows ≥ 2 evidence items**, or is labelled "Low confidence: limited evidence". Evidence types: posting counts and trends, survey responses, events, consultation quotes, placement outcomes, employer votes. |
| EXP-3 | Each evidence item shows: a summary sentence, the value, the period, the source type, `real` / `demo data`, and a link to the underlying records where possible. |
| EXP-4 | **Confidence** (High / Medium / Low) is shown next to every demand value, forecast and recommendation, with a tooltip explaining the rule. |
| EXP-5 | **Assumptions are visible** where used: coverage factor, completion rate, realisation factor, lag, staffing pattern. |
| EXP-6 | Forecasts are labelled "indicative", with a range, and simulated events are marked "Simulated". |
| EXP-7 | Candidate explanations use plain language: "Recommended because EV jobs in Nashik are rising, and 7 of 10 recent trainees from this course found jobs (demo data)." |
| EXP-8 | The About page (SCR-19) summarises every formula in plain language and shows the active config version. |
| EXP-9 | AI-produced content is labelled with its method (AIQ-5). |

---

## 16. Synthetic-data rules

| ID | Rule |
|---|---|
| SYN-1 | Every generated row has `is_synthetic = true`. Every UI value derived from it shows a **"demo data"** badge. |
| SYN-2 | Synthetic outcomes (placements, health scores) are attached **only to fictional institutes** ("Example ITI A" …), never to real institute names. |
| SYN-3 | Generation is **deterministic** (fixed seed) and documented in `docs/SYNTHETIC_DATA_SPEC.md`. |
| SYN-4 | Value ranges are **documented team assumptions**, never presented as real statistics. |
| SYN-5 | Simulated events are labelled "Simulated" in every screen and in the PDF. |
| SYN-6 | The PDF and the About page include a disclosure: which sections use demo data. |
| SYN-7 | The pitch never states synthetic results as real findings. We say "on synthetic data containing a planted pattern, the system detected…". |
| SYN-8 | **Planted patterns** must exist in the data, and the engines must rediscover them (see the table below). |

| ID | Planted pattern (synthetic) | Must be detected as |
|---|---|---|
| PP-1 | EV-charger installation and solar PV installation mentions rise over 4–6 quarters in Nashik and Pune | EMERGING skills; rising demand index |
| PP-2 | The Electrician course at Example ITI A, Nashik covers almost none of those skills | Coverage < 0.5 → OUTDATED; ADD_MODULE recommendations |
| PP-3 | A wiring-helper-type course in Kolhapur has more graduates than openings and low placement | OVERSUPPLIED; REDUCE_SEATS |
| PP-4 | A legacy skill (e.g. manual motor rewinding) declines over 4 quarters | DECLINING; DEMOTE_MODULE candidate |
| PP-5 | The simulated EV plant event in Nashik | Forecast uplift in quarters +2 to +5 |
| PP-6 | Institutes that already teach EV skills show better placement | Higher course health; ranked higher for candidates |

---

## 17. Demo requirements

### 17.1 Demo environment
| ID | Requirement |
|---|---|
| DEMO-1 | Runs offline on one presenter laptop. A second laptop has an identical setup as backup. |
| DEMO-2 | **Demo mode**: role switcher, "demo mode" banner, pre-seeded accounts (1 state officer, 1 district officer (Nashik), 1 institute admin (Example ITI A), 3+ Nashik employers, 1 admin, optionally 1 SSC reviewer). |
| DEMO-3 | Pre-seeded state = the start of the golden path. Two employer approvals are pre-seeded, so one live approval makes the recommendation VALIDATED (N = 3). |
| DEMO-4 | **Reset demo** restores the start state in ≤ 60 seconds (FR-18.1). |
| DEMO-5 | A recorded video of the full golden path (≤ 5 minutes) as a fallback. |
| DEMO-6 | Screens readable on a projector: large fonts on key numbers; no tiny tables in the golden path. |

### 17.2 Demo script (target 5 minutes)
| Time | Role | Screen | Presenter action | Audience must see |
|---|---|---|---|---|
| 0:00 | — | SCR-19 / title | One-line problem + "honest data" statement | Real vs demo data disclosure |
| 0:30 | Admin | SCR-17 | Simulate "EV component plant, Nashik, ~1,200 jobs" | Event created, labelled "Simulated" |
| 1:00 | State officer | SCR-02 | Show the map | Nashik mismatch highest |
| 1:20 | District officer | SCR-03 / SCR-04 | Open Nashik → EV technician role | EV skills EMERGING; forecast jump with range; confidence |
| 2:00 | Institute admin | SCR-08 | Open Electrician @ Example ITI A | Health score flagged OUTDATED; missing skills; curriculum diff; equipment and ToT needs; evidence |
| 2:50 | Employer | SCR-11 | Approve the change, comment, pledge 10 apprentices | Status → VALIDATED; pledge total updates |
| 3:30 | District officer | SCR-05 → SCR-06 | Add to plan → Generate PDF | PDF opens with the change, pledges, needs and disclosure |
| 4:10 | Candidate | SCR-12 / SCR-13 | Marathi: Nashik, 12th pass, EV | Top course with "why", career ladder, demo badge |
| 4:40 | — | — | Close: how the loop learns from outcomes; next steps (pilot) | — |

---

## 18. Acceptance criteria

### 18.1 Golden-path acceptance (the MVP is accepted only if all pass)
Starting from **Reset demo** on the presenter laptop:

| ID | Given / When / Then |
|---|---|
| GP-1 | **Given** the reset demo state, **when** the admin creates a simulated `NEW_PLANT` event for Nashik (EV, ~1,200 expected jobs), **then** within 60 s the Nashik forecast for EV-related roles rises in quarters +2 to +5, and the event shows the "Simulated" label. |
| GP-2 | **Given** GP-1, **when** the state officer opens SCR-02, **then** Nashik shows the highest mismatch score of the 4 districts, and the legend explains the colours in text. |
| GP-3 | **Given** GP-1, **when** the district officer opens Nashik on SCR-03, **then** at least 2 EV-related skills are labelled EMERGING, and at least 1 EV role is UNDERSUPPLIED, with confidence shown. |
| GP-4 | **Given** GP-3, **when** the institute admin opens Electrician @ Example ITI A (SCR-08), **then** coverage is < 0.5, the course is flagged OUTDATED, the health breakdown sums to the displayed score, and ≥ 1 ADD_MODULE change is shown with a draft outline, equipment needs and ToT needs. |
| GP-5 | **Given** GP-4, **when** the recommendation is opened, **then** it shows ≥ 2 evidence items, a confidence level, a priority, the decision owner and "demo data" badges where relevant. |
| GP-6 | **Given** 2 pre-seeded approvals, **when** a third Nashik employer approves on SCR-11 and pledges apprentices, **then** the status becomes VALIDATED, and the pledge total increases by the pledged amount. |
| GP-7 | **Given** GP-6, **when** the district officer adds it to the plan and clicks Generate PDF, **then** a PDF downloads within 15 s containing all FR-17.2 sections, the change (IN_PLAN), the vote counts, the pledge total, the equipment and ToT needs, and the synthetic-data disclosure. |
| GP-8 | **Given** GP-6, **when** a candidate completes SCR-12 in **Marathi** with Nashik / 12th pass / EV, **then** SCR-13 shows 3 courses in Marathi, the golden-path course ranks in the top 3, each shows a placement rate, salary range, "why", confidence and demo badge, and a career ladder with ≥ 1 next role. |
| GP-9 | **Given** any point in the flow, **when** the admin clicks Reset demo, **then** the start state is restored in ≤ 60 s, and GP-1…GP-8 can be repeated with identical results. |

### 18.2 Feature acceptance criteria (selected, P0)
| ID | Feature | Acceptance criterion |
|---|---|---|
| AC-1 | F1 | Loading demo data twice yields identical row counts. A file with an unknown district code produces rejected rows listed with reasons on SCR-14. |
| AC-2 | F1 | 100% of rows have provenance fields; 100% of synthetic rows have `is_synthetic = true` (checked on SCR-16). |
| AC-3 | F2 | The evaluation command prints precision, recall and F1 on the gold set, meeting AIQ-1. Hindi and Marathi aliases for at least the top 50 skills match their canonical skill. |
| AC-4 | F2 | Matches with confidence between 0.60 and 0.85 appear in the review queue. Accepting one updates the mapping, and it is used on the next run. |
| AC-5 | F3–F5 | For a hand-built test case (3 roles, 1 district), the demand index, openings, supply and ratio match hand calculations exactly. |
| AC-6 | F6 | For PP-1 and PP-4 data, the trend statuses are EMERGING and DECLINING respectively. For a flat series, STABLE. |
| AC-7 | F7 | With no events, the forecast equals the linear-trend baseline. With the simulated event, the uplift appears only in the configured lag window. |
| AC-8 | F8 | For a hand-built course, the health score and flags match hand calculations. The breakdown components sum to the score (± 1 for rounding). |
| AC-9 | F9 | ADD, UPDATE and DEMOTE rules each fire on a designed test case, and do not fire when their conditions are false. Every draft carries the "requires approval" label. |
| AC-10 | F10 | For an ADD_MODULE change, the required equipment excludes items the institute already has. The ToT need lists only skills no trainer covers at the required band. |
| AC-11 | F11 | Every recommendation has an evidence list, confidence, priority, status and decision owner. Every status change creates an audit entry. |
| AC-12 | F12 | A first-time user completes the survey in each of the 3 languages in ≤ 2 minutes. Submission without consent is blocked. Free-text skills are normalised. |
| AC-13 | F13 | An employer can vote once per recommendation and change their vote. The counts update immediately. Employers cannot see other districts' recommendations. |
| AC-14 | F14 | A pledge requires a positive integer and a timeframe. The totals on the recommendation, district dashboard and PDF are consistent. |
| AC-15 | F15 | The wizard works at 360 px width in all 3 languages. The results show the "guidance, not a guarantee" text. No personal data is requested or stored. |
| AC-16 | F16 | Every role has at least 1 ladder link or an explicit "top of ladder" marker. The skills to learn are listed for each step. |
| AC-17 | F17 | The PDF includes all required sections, the footer disclaimer and the disclosure. Only IN_PLAN items appear under "actions". |
| AC-18 | F18 | The data-quality page lists all checks in §18.3 with pass or fail. Reset meets DEMO-4. |
| AC-19 | F19 | Simulated events are labelled everywhere, can be deleted, and are removed by reset. |
| AC-20 | Auth | Each role can reach only its screens. Calling another role's API returns an authorisation error. |
| AC-21 | AI | With the LLM switch **off**, all P0 flows work (AIQ-3). With it on, cached responses make repeated runs identical. |
| AC-22 | Explainability | A random sample of 10 displayed scores each opens a breakdown. A random sample of 5 recommendations each shows ≥ 2 evidence items or the low-confidence label. |

### 18.3 Data-quality checks (shown on SCR-16)
- DQ-1: Every district reference exists in the district list.
- DQ-2: Every skill, role and course reference exists.
- DQ-3: Provenance fields are complete.
- DQ-4: Synthetic flags are present on synthetic files.
- DQ-5: Duplicate postings ≤ 2% after deduplication.
- DQ-6: Unmapped place names ≤ 5%.
- DQ-7: Postings with zero extracted skills ≤ 15%.
- DQ-8: Every role has ≥ 5 skills; every MVP course has ≥ 1 mapped role.
- DQ-9: Planted patterns PP-1…PP-6 are detected.

### 18.4 Definition of "MVP done"
- [ ] GP-1…GP-9 pass on the presenter laptop, 3 rehearsals in a row
- [ ] AC-1…AC-22 pass
- [ ] DQ-1…DQ-9 pass
- [ ] The About page lists all sources, attributions and the synthetic disclosure
- [ ] The backup video is recorded; the backup laptop is set up
- [ ] README lets a new teammate set up and run the demo on Windows in ≤ 30 minutes

---

## 19. Delivery plan, cut list, risks

### 19.1 Milestones (aligned with the 3-week prep + 36-hour final)
| Milestone | When | Exit criteria |
|---|---|---|
| M0: Docs & data sprint | End of week 1 | PRD agreed; reference data (districts, roles, skills, 4–6 courses) curated; synthetic spec written |
| M1: Walking skeleton | Mid week 2 | Login + role switch; demo data loads; SCR-02 and SCR-03 show real computed numbers for 1 district |
| M2: Engines complete | End of week 2 | F2–F11 computed; AC-5…AC-11 unit tests pass; the planted patterns are detected |
| M3: Golden path complete | Mid week 3 | GP-1…GP-9 pass once; employer, candidate and PDF screens done |
| M4: Demo-ready | End of week 3 | Definition of MVP done met; the video is recorded |
| Finale (36 h) | Hackathon | Only fixes, polish, P1 items if everything is green, and judge-requested tweaks |

### 19.2 Cut list (if behind schedule, cut in this order)
1. All P1 items (SSC screen, config editor, Telegram bot, chat assistant, Marathi / Hindi PDF, cost estimates)
2. LLM-based enhancements (keep the template and rule-based P0 approaches)
3. The map on SCR-02 → replace it with a ranked table plus coloured badges
4. Hindi on candidate and employer screens (keep **English + Marathi**)
5. The forecast range band (keep the line with the "indicative" label)
6. Districts other than Nashik in the UI (the engines still compute all 4; the UI focuses on Nashik)

**Never cut:** evidence and confidence display, synthetic badges, Reset demo, the PDF, candidate guidance in Marathi, employer validation and pledges.

### 19.3 Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Scope creep | Golden path unfinished | Golden-path rule (§2); P0/P1 labels; weekly scope review |
| Data collection delays | Engines have nothing real to run on | The synthetic data spec comes first; real data replaces it gradually |
| Unverified official details | Credibility loss with judges | TODO-VERIFY list; only `TEAM_VERIFIED` facts in the pitch |
| AI service unavailable or costly | Demo failure | AIQ-3 off-switch; caching; rule-based P0 |
| Devanagari rendering issues | Broken candidate / PDF text | Test the fonts early (week 2); English PDF is P0 |
| Demo-day failure (network, laptop) | Lost demo | Offline setup, backup laptop, video, reset button |
| Judges question realism ("who changes ITI syllabi?") | Credibility | The decision-owner routing (FR-9.5) and the "proposes, doesn't decide" message |

### 19.4 Open questions for the team
1. Which 4–6 courses exactly? (Proposed: DGT Electrician, Solar Technician (Electrical), Mechanic Electric Vehicle, plus 1 solar and 1 EV SSC short course — confirm after data verification.)
2. Is N = 3 approvals right for VALIDATED, given small demo numbers?
3. Should the state officer also be able to generate plans, or only the district officer?
4. How many real employer survey responses can we realistically get by the end of week 2?

---

*Change log*
- v0.1: first complete MVP PRD for team review.
