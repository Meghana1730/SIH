# KaushalSetu — Domain Primer

| | |
|---|---|
| **File** | `docs/01-domain.md` |
| **Audience** | The whole KaushalSetu team (6 people) |
| **Status** | Draft v0.1 |
| **Read time** | About 45 minutes. Everyone should read it fully before we write code. |

---

## Before you read

- **Why this document exists.** A data product like KaushalSetu fails far more often from *misunderstanding the domain* than from bad code. Before we build anything, all six of us must use the same words for the same things.
- **All examples are made up.** Every number, institute, company and event in the examples exists only to explain a concept. None of them is a real statistic or a real claim about any institute or company.
- **TODO-VERIFY** marks anything that must be confirmed from an official source before we use it in the product or the pitch. [Section 19](#19-what-must-be-officially-verified-and-where) collects all of them.
- **Simplifications.** Government structures, schemes and rules change over time. The descriptions here are simplified for learning. **Where this document and an official source disagree, the official source wins.**

---

## Contents

1. [What problem KaushalSetu solves](#1-what-problem-kaushalsetu-solves)
2. [Who uses it](#2-who-uses-it)
3. [The Indian skill-development ecosystem: key terms](#3-the-indian-skill-development-ecosystem-key-terms)
4. ["Skill" as the common language](#4-skill-as-the-common-language)
5. [Demand vs supply: a simple example](#5-demand-vs-supply-a-simple-example)
6. [What a Skill Graph means in our system](#6-what-a-skill-graph-means-in-our-system)
7. [Job posting data](#7-job-posting-data)
8. [Employer survey data](#8-employer-survey-data)
9. [Industry events and other industry signals](#9-industry-events-and-other-industry-signals)
10. [Placement outcomes](#10-placement-outcomes)
11. [Curriculum alignment](#11-curriculum-alignment)
12. [Employer validation](#12-employer-validation)
13. [Candidate guidance](#13-candidate-guidance)
14. [Evidence and provenance](#14-evidence-and-provenance)
15. [Synthetic data and why we need it](#15-synthetic-data-and-why-we-need-it)
16. [Data vs metric vs signal vs recommendation vs validation](#16-data-vs-metric-vs-signal-vs-recommendation-vs-validation)
17. [The complete KaushalSetu loop: the Nashik EV example](#17-the-complete-kaushalsetu-loop-the-nashik-ev-example)
18. [Terms to understand before coding](#18-terms-to-understand-before-coding)
19. [What must be officially verified, and where](#19-what-must-be-officially-verified-and-where)

---

## 1. What problem KaushalSetu solves

### The situation

India trains a very large number of young people for jobs through ITIs, polytechnics and short-term schemes such as PMKVY. These programmes are planned using occupation categories and syllabi that change slowly. Industry changes quickly. For example, electric vehicles, rooftop solar and smart meters create new tasks that older syllabi may not cover.

When training and industry drift apart, everyone loses:

| Who | What can go wrong |
|---|---|
| **Trainee** | Finishes a course, then finds that local employers want different skills. The result is weak placement. |
| **Employer** | Cannot find job-ready candidates, so spends time and money retraining new hires. |
| **Institute** | Does not know which modules are outdated. Equipment and trainer skills may be planned for yesterday's jobs. |
| **Government planner** | Plans seats using broad or old categories and cannot see changing *local* demand in time. |

### Why it keeps happening (root causes)

1. **Different languages.** Employers describe needs as job roles and tools ("EV charger technician"). Institutes describe training as courses and trades ("Electrician trade"). With no common unit, the two can't be compared.
2. **Different speeds.** Demand can change within months. Curricula are revised over years.
3. **Invisible demand.** Many jobs, especially in small businesses (MSMEs) and the informal sector, are never posted online.
4. **No feedback.** Placement results rarely flow back into decisions about what to teach.
5. **Disconnected planning.** A new module also needs equipment, trained trainers and new assessments. These are often planned separately.
6. **Low trust in numbers.** Decision-makers need to see *why* a change is recommended, not just a score.
7. **Blind choices.** Candidates choose courses without seeing local job outcomes.

### What KaushalSetu does

KaushalSetu runs a **continuous, evidence-based loop**:

```
INDUSTRY DEMAND → SKILLS → DISTRICT DEMAND → TRAINING SUPPLY → DEMAND/SUPPLY GAP
      ↑                                                                   ↓
FEEDBACK ← PLACEMENT OUTCOMES ← EMPLOYER VALIDATION ← CURRICULUM RECOMMENDATIONS ← COURSE HEALTH
```

| Step | In plain words |
|---|---|
| Industry demand | Collect signs of what employers need: job postings, surveys, industry events, consultations, trends. |
| Skills | Translate every job and every course into a common unit: **skills**. |
| District demand | Estimate how much of each skill and role each district needs, per time period. |
| Training supply | Estimate how many trained people each district produces for each role and skill. |
| Gap | Compare demand and supply to find shortages, surpluses and missing skills. |
| Course health | Score each course on placement, relevance and skill coverage. |
| Curriculum recommendations | Suggest specific changes (add, update or demote modules; change seats; train trainers; buy equipment), each with evidence. |
| Employer validation | Employers confirm or reject the suggestions, and can pledge hires or apprenticeships. |
| Placement outcomes | Track what actually happened to trainees after training. |
| Feedback | Use the outcomes to improve the next round of estimates. |

### What KaushalSetu is NOT

- **Not a job portal.** It uses job data, but its purpose is planning and guidance.
- **Not a learning platform.** It does not deliver lessons.
- **Not an approving authority.** It does not approve curricula or qualifications. It prepares **evidence-backed proposals** for the people and bodies who do.
- **Not a replacement for official portals.** Official systems such as the National Career Service or Skill India Digital Hub stay in place. KaushalSetu would *use* their data and *feed* them decisions. Real integration is future work.

---

## 2. Who uses it

| User | Example person | The question they ask | What KaushalSetu gives them | What they give back to the loop |
|---|---|---|---|---|
| **District / state skill official** | A member of a District Skill Committee | "Which courses should my district expand, shrink or change next year?" | District map of gaps, gap tables, a **draft district training plan** | Approved plans, implementation status |
| **Institute head** (ITI, PMKVY training centre, polytechnic) | An ITI principal | "Are my courses still relevant? What exactly should change?" | **Course health score**, curriculum recommendations, trainer and equipment needs | Course, seat, trainer, equipment and placement data |
| **Sector Skill Council (SSC) reviewer** | A curriculum expert at an SSC | "Which job standards (QPs/NOS) need revision?" | Emerging and declining skills across districts, with evidence | Approval or rejection of proposed modules |
| **Employer** | HR at an EV service company; owner of a small solar installation firm | "Where do I find people with the right skills? Will courses teach what I need?" | A way to validate proposed changes and to find candidates | Survey answers, votes, pledges, ratings of hires |
| **Candidate** | A 12th-pass youth in Nashik | "Which course near me leads to a job?" | Course suggestions with **local** outcomes and career paths, in their language | Profile (with consent), course choice, placement status |
| **Platform admin** | Our team | "Is the data healthy and are the results sensible?" | Review queues, data-quality checks, settings | Corrections to mappings, approved configuration changes |

> **Prototype note:** in the hackathon prototype, all of these users are **simulated with demo accounts**. We do not claim to have real officials, institutes or employers using it.

---

## 3. The Indian skill-development ecosystem: key terms

### A simplified map

```
                 Ministry of Skill Development & Entrepreneurship (MSDE)
                                         │
          ┌──────────────────────────────┼───────────────────────────────┐
          ▼                              ▼                               ▼
         DGT                           NCVET                            NSDC
  (long-term training,          (regulator; oversees            (supports Sector Skill
   ITIs, instructor              NSQF; approves                  Councils and skilling
   training)                     qualifications)                 schemes such as PMKVY)
          │                              │                               │
  CTS: trades run in ITIs,      Approved qualifications          Sector Skill Councils (SSCs)
  DGT publishes syllabi         are listed on the NQR            write Qualification Packs (QPs),
                                                                 which are made of NOS

  Ministry of Labour & Employment → NCS portal (jobs, career services); NCO occupation codes
  Technical education system (AICTE, state technical boards) → Polytechnics (diplomas)
  District Skill Committee → District Skill Development Plan
```

> **TODO-VERIFY:** this map is simplified for learning. Before using it in the pitch, confirm the current roles and relationships from each body's official website.

Each term below follows the same pattern: **what it is**, **a simple way to think about it**, and **why it matters to KaushalSetu**.

### 3.1 ITI — Industrial Training Institute
- **What it is:** A government or private institute offering long-term, hands-on vocational training in **trades** such as Electrician, Wireman, Fitter or motor-vehicle mechanic. Entry qualification and duration vary by trade. *(TODO-VERIFY per trade in the DGT syllabus.)*
- **Think of it as:** a trade school, a practical college for a specific craft.
- **Why it matters:** ITIs are a major source of trained people for our sector (electrical trades). Their trade syllabi are set **centrally** under DGT, so an individual ITI generally cannot rewrite a trade syllabus on its own. Our recommendations must respect this *(see [Section 11](#11-curriculum-alignment))*.

### 3.2 Polytechnic
- **What it is:** An institution offering **diploma** programmes in engineering and technology, such as a diploma in electrical engineering. It sits in the **technical education** system, not the short-term skilling system. Approval and curriculum involve bodies such as AICTE and state technical education boards. In Maharashtra that board is **MSBTE**. *(TODO-VERIFY roles and entry rules.)*
- **Think of it as:** the level above an ITI, often producing technicians and supervisors.
- **Why it matters:** Polytechnic graduates supply higher-level roles, such as supervisors and senior technicians in EV and solar. Their syllabi are *not* usually built on SSC Qualification Packs. We still map them to skills the same way.

### 3.3 PMKVY — Pradhan Mantri Kaushal Vikas Yojana
- **What it is:** A flagship MSDE scheme for **short-term skill training** and **Recognition of Prior Learning (RPL)**. RPL means certifying skills that people already gained through work. Courses are run by training centres and are generally aligned to Qualification Packs. The scheme has run in several phases. *(TODO-VERIFY the current phase, rules and implementation structure.)*
- **Think of it as:** a short, job-focused course, typically weeks to months rather than years. *(TODO-VERIFY typical durations.)*
- **Why it matters:** Short courses can be started or changed faster than long ITI trades. This makes them the **quickest lever** for filling a newly discovered skill gap.

### 3.4 NSQF — National Skills Qualifications Framework
- **What it is:** A national framework that arranges qualifications into **levels** by complexity: what a person knows, what they can do, and how much responsibility they can take. A higher level means more complex work with more independence. The framework has been revised over time. *(TODO-VERIFY the current number of levels and their official descriptors on the NCVET website.)*
- **Think of it as:** school classes (Class 5 vs Class 10), but for work ability instead of academics.
- **Why it matters:** It gives us an official way to express **proficiency level**. Every job, qualification and course outcome in our system should carry a level where one is officially available.

### 3.5 NCVET — National Council for Vocational Education and Training
- **What it is:** The **regulator** for vocational education and training. Its roles include approving qualifications, recognising awarding bodies and assessment agencies, and overseeing the NSQF. *(TODO-VERIFY the exact list of functions.)*
- **Think of it as:** the referee that decides which qualifications are officially valid.
- **Why it matters:** Any official change to a qualification goes through regulated processes. KaushalSetu **supplies evidence** to those processes. It never bypasses them.

### 3.6 SSC — Sector Skill Council
- **What it is:** An **industry-led** body for one sector, such as automotive, electronics, green jobs or power. SSCs define job roles and their standards (QPs and NOS) and are involved in assessment and certification.
- **SSCs likely relevant to us (TODO-VERIFY each on the NQR):**
  - Skill Council for Green Jobs (solar PV roles)
  - Automotive Skills Development Council (EV roles)
  - Electronics Sector Skills Council of India
  - Power Sector Skill Council
- **Think of it as:** the industry's official voice on what a job requires.
- **Why it matters:** SSCs are the natural reviewers of our "this standard needs updating" evidence. In our product they have their own reviewer role.

### 3.7 QP — Qualification Pack
- **What it is:** The official description of **one job role**. It lists the role name, sector, NSQF level, entry requirements and the set of **NOS** a person must meet. Each QP has an official code, a version and a validity period.
- **Think of it as:** a recipe card for a job. The NOS are its ingredients.
- **Why it matters:** A QP is a ready-made bridge between a *job role* and a *set of skills*. We will import the QPs relevant to our sector.
- **Rule for our team:** **never guess a QP code.** Look up every code on the NQR and record where it came from. *(TODO-VERIFY codes for all our roles.)*

### 3.8 NOS — National Occupational Standard
- **What it is:** One **unit of competence** inside a QP. It describes a specific work function, **what** the person must be able to do and **to what standard** (performance criteria), and the **knowledge and understanding** needed.
- **Illustrative example (not an official NOS):** *"Install a rooftop solar mounting structure"*. Performance criteria might include checking the roof condition, following safety procedures and fixing the structure as per the design.
- **Think of it as:** one line of the recipe, described in enough detail that an assessor can check it.
- **Why it matters:** NOS are the closest official thing to our "skills". We map each NOS to one or more skills in our Skill Graph. When we recommend a new module, we try to link it to an existing NOS.

### 3.9 NQR — National Qualification Register
- **What it is:** The official register of approved NSQF-aligned qualifications. It is where you look up a QP's code, level, version and validity. *(TODO-VERIFY how to access it and its terms of use.)*
- **Think of it as:** the official phone directory of qualifications.
- **Why it matters:** It is our **source of truth** for QPs and NOS. Every QP or NOS in our data should record the NQR entry it came from.

### 3.10 DGT and CTS
- **DGT (Directorate General of Training):** under MSDE, responsible for long-term vocational training, including ITIs, apprenticeship training and instructor training. *(TODO-VERIFY current scope.)*
- **CTS (Craftsmen Training Scheme):** the scheme under which ITIs run their trades. DGT publishes the **syllabus for each trade**: topics, hours, practical exercises and, typically, a list of tools and equipment. *(TODO-VERIFY that the syllabi for our trades include equipment lists.)*
- **Related:** DGT also runs instructor training for ITI trainers. One such scheme is the Craft Instructor Training Scheme. *(TODO-VERIFY.)* This matters for our trainer-development recommendations.
- **Why it matters:** CTS trade syllabi are our main **supply-side documents**, because they tell us what ITIs actually teach. Their equipment lists help us plan equipment needs.

### 3.11 NCS — National Career Service
- **What it is:** A service and portal of the Ministry of Labour & Employment that connects job seekers and employers. It lists vacancies and job fairs and offers career guidance.
- **Why it matters:** It is a potential **official source of job-posting data** *(TODO-VERIFY data access and terms of use)*, and a natural future home for our candidate guidance.

### 3.12 District Skill Development Plan
- **What it is:** A plan for one district. It describes the district's economy, skill demand, training supply, gaps and planned actions. It is usually prepared through a **District Skill Committee**, a district-level committee, typically chaired by the District Collector. *(TODO-VERIFY.)* This planning approach was promoted under MSDE's **SANKALP** programme. *(TODO-VERIFY current guidance, template and programme status.)*
- **Why it matters:** This is exactly the document our **district training plan** output imitates. If KaushalSetu drafts it automatically, with evidence, officials save time on work they already have to do. That is our strongest adoption argument.

### 3.13 Other terms you will hear

| Term | Meaning (simplified) |
|---|---|
| **MSDE** | Ministry of Skill Development & Entrepreneurship. The central ministry for skilling. |
| **NSDC** | National Skill Development Corporation. Supports SSCs, training partners and skilling schemes. *(TODO-VERIFY role.)* |
| **SIDH** | Skill India Digital Hub. The national digital platform for skilling. *(TODO-VERIFY scope.)* |
| **Training partner / training centre** | An organisation, or one of its centres, that delivers courses under a scheme. |
| **Assessment agency** | An organisation that tests trainees against the QP/NOS before certification. |
| **RPL** | Recognition of Prior Learning. Certifying skills gained through work experience. |
| **ToT** | Training of Trainers. Training that prepares trainers to teach a new topic. |
| **Apprenticeship** | Paid on-the-job training with an employer under the apprenticeship rules and schemes. *(TODO-VERIFY which scheme applies to ITI-level trainees.)* |
| **NCO** | National Classification of Occupations. Official occupation codes from the Ministry of Labour & Employment. *(TODO-VERIFY the current edition and the codes for our roles.)* |
| **LGD code** | Local Government Directory code. An official unique code for each district, useful as a stable district ID. |
| **PLFS** | Periodic Labour Force Survey. An official labour survey. *(TODO-VERIFY whether its estimates are reliable at district level. They may only be reliable at state level.)* |
| **MSME / Udyam** | Micro, Small & Medium Enterprises. **Udyam** is the MSME registration system. *(TODO-VERIFY what data is publicly available by district.)* |
| **DVET (Maharashtra)** | The state directorate for vocational education and training, which oversees ITIs in Maharashtra. *(TODO-VERIFY name and role.)* |
| **DPDP Act, 2023** | The Digital Personal Data Protection Act. India's law on handling personal data. *(TODO-VERIFY the current rules and their status.)* |

---

## 4. "Skill" as the common language

### The core idea

Industry and education describe the same world in different words. Nothing can be compared until both are translated into one shared unit. In KaushalSetu, **that unit is a skill at a proficiency level**.

| What an employer writes (job ad) | What an institute writes (syllabus) | The common skill (illustrative) |
|---|---|---|
| "Solar technician needed, rooftop experience" | "Module: Non-conventional energy sources" | Install and commission rooftop solar PV systems |
| "EV charger installation, must know safety" | *(nothing)* | Install and commission EV charging equipment; Apply high-voltage safety procedures |
| "Wiring helper for new buildings" | "Domestic wiring practice" | Carry out domestic electrical wiring |

Once both sides are expressed as skills, the comparison becomes easy. In this example, the syllabus has **no match** for EV charger installation. That is a gap.

### What counts as a skill in KaushalSetu

A **skill** is a specific ability to perform a work task that:
1. **can be taught** in a module,
2. **can be checked** in an assessment, and
3. **an employer would recognise** in a job ad.

| Too broad ❌ | Just right ✅ | Too narrow ❌ |
|---|---|---|
| "Electrical work" | "Carry out domestic wiring as per safety standards" | "Strip a 2.5 sq mm wire" |
| "EV knowledge" | "Test and diagnose faults in an EV battery pack" | "Read one brand's specific error code" |

### Types of skills

| Type | Example |
|---|---|
| Technical | Install a rooftop solar PV system |
| Tool / equipment | Use an insulation resistance tester |
| Safety | Apply lockout-tagout before electrical work *(lockout-tagout: locking and labelling a power source so nobody switches it on during repair)* |
| Domain knowledge | Understand how panel direction and tilt affect solar output |
| Core / soft | Explain a fault clearly to a customer |

### Skill vs related words

| Word | Meaning | Example |
|---|---|---|
| **Job role** | A job made up of many skills | Solar PV Installer |
| **Skill** | One ability | Mount PV modules on a rooftop structure |
| **Knowledge** | What you must know to perform the skill | Why panels must be earthed |
| **Tool** | Equipment used to perform the skill | Multimeter |
| **Course / module** | How skills are taught | A 40-hour "Solar basics" module *(illustrative)* |
| **Qualification (QP)** | The official standard for a role | The official QP for a solar role *(TODO-VERIFY on NQR)* |

### Proficiency level: the same skill at different depths

"Knows solar installation" is not enough. A helper and a supervisor both "know" it, but at very different depths. Our **working bands** are our own simplification. We must map them carefully to the official NSQF level descriptors. *(TODO-VERIFY.)*

| Band | What the person can do | Typical title |
|---|---|---|
| 1 — Assist | Simple tasks under supervision | Helper |
| 2 — Perform | Standard tasks independently | Technician / Installer |
| 3 — Diagnose | Non-routine problems; checks others' work | Senior technician |
| 4 — Lead | Plans work, supervises, ensures compliance | Supervisor |

### Aliases and languages

One skill has many names. "Solar fitting", "PV installation", "rooftop solar work", Hindi **"सोलर पैनल लगाना"** and Marathi **"सोलर पॅनल बसवणे"** should all point to **one** skill in our system. We keep a list of **aliases** (alternative names) for each skill, in all three of our languages.

---

## 5. Demand vs supply: a simple example

### Definitions

- **Demand:** how many people with a particular role or skill employers will need, **in a particular place, during a particular period**.
- **Supply:** how many trained people will become available for that role or skill, **in the same place and period**.
- **Gap:** the difference between them. We often use the **ratio** `supply ÷ demand`.

**Think of a vegetable market.** If 100 families want tomatoes and only 30 kg arrive, there is a shortage. If 300 kg arrive, much of it is wasted. Skills behave the same way.

### Illustrative example (made-up numbers)

**Nashik: solar PV installers, next 12 months**
- Demand estimate: **300** openings
- Supply: 2 relevant courses with 100 seats filled. About 80% complete the course, so **80** trained people.
- Ratio: 80 ÷ 300 = **0.27** → a strong **shortage** (undersupplied)

**Kolhapur: wiring-helper-type role, next 12 months**
- Demand estimate: **60** openings
- Supply: **150** trained people
- Ratio: 150 ÷ 60 = **2.5** → a **surplus** (oversupplied)

**Our working thresholds** (a starting proposal, to be tuned later):

| Ratio (supply ÷ demand) | Meaning |
|---|---|
| Below 0.7 | Undersupplied (shortage): expand or add training |
| 0.7 to 1.5 | Roughly balanced |
| Above 1.5 | Oversupplied (surplus): review, reduce or redirect seats |

### Watch out

- **Job postings are not demand.** Many jobs are never posted, and some are posted many times.
- **Seats are not supply.** Some trainees drop out, go for further study, move away or don't look for jobs.
- **Districts leak.** People commute and migrate across district borders.
- **Shortages can hide inside a role.** A district may have enough electricians overall but too few *who know solar*. That is why we measure demand at the **skill** level as well as the **role** level.
- **Always state the period.** "Demand" without a time period is meaningless.

---

## 6. What a Skill Graph means in our system

### What a "graph" is

In computer science, a **graph** is a set of **things** (called *nodes*) and **connections** between them (called *edges*). A metro map is a graph: stations are nodes, and the lines between them are edges. A family tree is another.

### Our Skill Graph

The **Skill Graph** is KaushalSetu's map of how everything connects through skills.

**Nodes (things):** job role, skill, proficiency level, QP, NOS, course, course module, institute, district, trainer, equipment, employer, candidate.

**Edges (connections), with what each one means:**

| Connection | Meaning |
|---|---|
| Job role → **needs** → Skill | This job requires this skill, with an importance and a required level |
| QP → **contains** → NOS → **covers** → Skill | The official standard for a role, broken down into skills |
| Course → **has** → Module → **teaches** → Skill | What the course actually teaches, and at what level |
| Trainer → **can teach** → Skill | Which trainers can teach which skills |
| Skill → **requires** → Equipment | What equipment is needed to teach a skill |
| Candidate → **has** → Skill | What a person can do, and how that was verified |
| Job role → **leads to** → Job role | Career steps: the next role is reachable with a small skill gap |

### A tiny example (illustrative)

```
[Role: EV Charging Technician] ──needs (high importance, band 2)──▶ [Skill: Install EV charger]
                                                                        ▲         │
                     [Module: "EV basics"] ──teaches (band 1)───────────┘         │
                              ▲                                                   │
                     [Course: Electrician, Example ITI A]                  requires
                                                                                  ▼
[Trainer: T-03] ──can teach (band 2)──▶ [Skill: Install EV charger]    [Equipment: EV charger training unit]
```

Reading this graph, we can tell that the course teaches this skill only at band 1, while the job needs band 2. That is a **level gap**. Trainer T-03 can teach it, and the institute needs an EV charger training unit.

### Questions the Skill Graph lets us answer

- Which courses in Nashik teach the skills an EV technician needs? What is missing?
- Which trainers can already teach the missing skills, and who needs training?
- What equipment does a new module require?
- What is a realistic next career step for someone with these skills?

> **Good to know:** a Skill Graph does not need a special "graph database". We can store it in ordinary database tables. It also **grows over time**: new skills are discovered in job ads, and uncertain connections are sent to a human for review.

---

## 7. Job posting data

### What it is

A **job posting** is an advertisement for a job. It usually contains a title, a description, a location, a salary range, an experience requirement, a date and an employer name.

### Where it can come from

- Official portals such as the National Career Service *(TODO-VERIFY access and terms)*
- Public job-posting datasets *(TODO-VERIFY each dataset's license)*
- Job websites, **only** where their terms of use allow it

> **Rule:** we do not scrape any website in a way its terms of use forbid.

### What we extract from a posting

| Field | Example |
|---|---|
| Job role | EV charging technician *(mapped to an official occupation where possible — TODO-VERIFY codes)* |
| Skills | EV charger installation; electrical safety; multimeter use |
| Proficiency | Inferred from experience and wording, e.g. "fresher" → band 1–2 |
| District | Messy text like "Ambad MIDC, Nashik" → Nashik district |
| Salary, experience, date | As stated |

### Illustrative posting (fictional)

> **EV Charging Technician (Fresher / 1 year)** — Example Company, Nashik
> ₹15,000–18,000 per month. ITI Electrician required. Knowledge of EV charger installation, safety procedures and basic multimeter use. Two-wheeler preferred.

What we would extract:
- **Skills:** EV charger installation (band 2), electrical safety procedures (band 2), multimeter measurement (band 2)
- **Qualification:** ITI Electrician
- **Not a skill:** "Two-wheeler preferred" is a **job condition**, not a skill. Our extraction must learn this difference.

### Problems with job posting data

| Problem | What it means | How we handle it |
|---|---|---|
| Duplicates | The same job is posted several times or on several sites | Detect and merge them (**deduplication**) |
| Vague titles | "Technician" could mean anything | Rely on the description, not just the title |
| Messy locations | Area names, industrial estates, spelling variations | Keep a list mapping place names to districts |
| Bias | Online postings over-represent big, urban, formal employers | Combine with surveys of small employers (Section 8) |
| Postings ≠ hires | A posting may never be filled | Treat postings as a *signal*, not a count of jobs |
| Personal data | Some ads contain phone numbers or names | Do not store personal contact details |

---

## 8. Employer survey data

### What it is

Short questionnaires in which employers tell us directly what they need.

### Why we need it

Many small employers never post jobs online. A survey is how we **make invisible demand visible**. It also captures things job ads rarely say, such as "freshers lack safety knowledge".

### What we ask (keep it under 2 minutes)

1. Which roles do you expect to hire for in the next 12 months?
2. Roughly how many people for each role?
3. Which skills are hardest to find?
4. What level do you need: helper, technician, senior or supervisor?
5. Would you offer apprenticeships if courses taught these skills?
6. Which district is the job in?

### Channels and languages

- Simple web form, plus a chat bot on a messaging app (Telegram for the prototype; WhatsApp possibly later)
- English, Hindi and Marathi
- Phone calls, which a team member can record into the form

### Problems and how we handle them

| Problem | How we handle it |
|---|---|
| Small samples | Show a **confidence level**; never present one survey as proof |
| Optimism: employers over-estimate hiring | Weight surveys together with other signals |
| Survey fatigue | Keep it short, and ask rarely |
| Same employer answering twice | Keep the **latest** answer per employer |

### Illustrative response (fictional)

> Example Solar Installers, Nashik (small business): need **8 installers** in the next 6 months. Hardest skill to find: **"rooftop safety and earthing"**. Willing to take **3 apprentices**.

---

## 9. Industry events and other industry signals

### Industry events

An **industry event** is something that happens in the economy and is likely to change the demand for skills in the future:

- A new factory or plant is announced, or an existing one expands
- A plant closes or cuts staff
- A new government policy or incentive (e.g. for rooftop solar or EVs)
- A large project (e.g. a charging network rollout)
- A technology shift in an industry

### Key ideas

| Idea | Meaning |
|---|---|
| **Leading indicator** | A sign that comes *before* the change. An announcement today may mean hiring in 1–2 years. |
| **Lag** | The delay between an event and actual hiring |
| **Realisation** | Announced ≠ built ≠ hired. Only part of the announced jobs may appear, so we apply a **realisation factor** (an assumption we must state). |
| **Staffing pattern** | How total jobs split into roles, e.g. "of 1,000 plant jobs, some share are electricians". This is our **assumption**, to be checked with employers. *(TODO-VERIFY with industry.)* |
| **Source quality** | An official announcement is stronger evidence than a rumour in the news |

### Other industry signals

- **Industry consultations:** notes from meetings with employers or associations. We extract skills, problems and **quotes** (e.g. *"Freshers don't know high-voltage safety"*). They are anecdotal, but excellent as evidence.
- **Sector growth data:** official statistics and MSME registration data *(TODO-VERIFY availability and reliability at district level)*.
- **Emerging-technology trends:** signs that a skill is rising nationally or globally before it appears locally, from industry reports and national job trends.

### Illustrative event (hypothetical, not real)

> *"An EV component manufacturer announces a facility in Nashik, expected to create 1,200 jobs over two years."*
> KaushalSetu would spread the expected demand over future quarters (after a lag), split it across roles using the staffing pattern, and apply a realisation factor. The result is a raised **forecast** for EV-related roles in Nashik.

---

## 10. Placement outcomes

### What it is

What happened to trainees **after** training.

| Field | Example |
|---|---|
| Placed or not | Yes |
| Employer and role | Example EV Services, EV charging technician |
| Salary | ₹16,000 per month |
| Date placed | 3 months after completing |
| Still employed after 6 months (**retention**) | Yes |
| Job related to training? | Yes |
| Employer rating of the hire | 4 out of 5 |

### Metrics we calculate from it

- **Placement rate** = placed trainees ÷ trainees who completed
- **Median salary** of placed trainees. The median is the middle value, which is safer than the average because a few very high salaries don't distort it.
- **Retention rate** = still employed after 6 months ÷ placed
- **Relevance rate** = placed in a job related to the training ÷ placed

### Why it matters most

Placement outcomes are the **final test** of whether a course works. They close the loop: if our recommendations were right, outcomes should improve, and we use them to adjust our scoring.

### Watch out

- **"Placed" is defined differently** across schemes and institutes. *(TODO-VERIFY the official definitions for the schemes we reference.)*
- **Self-employment** (e.g. a trainee starting their own solar repair work) is a real outcome and must be counted properly.
- **Self-reported data** can be inflated. Mark each outcome as *verified* or *unverified*.
- **Small groups:** a 10-person batch with 9 placed is less reliable than 200 with 150 placed. Show confidence.
- **Privacy:** outcomes are personal data. Use them only in aggregated form for officials (see [Section 13](#13-candidate-guidance)).

---

## 11. Curriculum alignment

### What it is

**Curriculum alignment** means checking how well a course teaches the skills that local employers need, and proposing specific changes where it doesn't.

### How it works (in concept)

1. Translate the course's modules into skills and levels (from the syllabus).
2. Take the skills that are in demand in the district, weighted by importance and trend.
3. Calculate **coverage**: the share of important demanded skills that the course teaches at the required level.
4. Combine coverage with placement, salary, retention and demand trend into a **course health score** (0–100).
5. Where coverage is low, generate **recommendations**.

### Course health score, in plain words

A single number summarising "is this course still worth running as it is?". It is always shown **with its breakdown**, e.g. *placement: good, coverage: poor, demand trend: rising*, so nobody has to trust a bare number.

### Types of recommendations

| Type | Meaning |
|---|---|
| **Add module** | Teach a missing, in-demand skill |
| **Update module** | Teach an existing skill at a deeper level |
| **Demote to elective** | A low-demand topic becomes optional. Only after human validation. |
| **Remove module** | Only with strong evidence **and** official approval |
| **Expand / reduce seats** | Based on shortage or surplus |
| **New course** | A role is in shortage and no course in the district teaches it |
| **Train trainers (ToT)** | No current trainer can teach a newly needed skill |
| **Equipment** | A new skill needs equipment the institute lacks |
| **Assessment update** | New skills need new assessment criteria, ideally linked to NOS performance criteria |

### Illustrative curriculum diff (made up)

| Change | Module | Evidence (summary) | Also needs |
|---|---|---|---|
| ADD | EV charging installation and high-voltage safety | Rising EV-charger postings; 4 employer surveys; consultation quote on safety | 2 EV charger training units, safety kits, ToT for 2 trainers |
| UPDATE | Battery basics → battery testing (band 2) | Employers ask for testing, not just theory | Battery tester |
| DEMOTE | A low-demand legacy topic → elective | Declining mentions over 4 quarters | Only after employer and SSC review |

### Who can actually change a curriculum? (critical for realism)

KaushalSetu **proposes**. The right authority **decides**. We must route each recommendation to the right place.

| Course type | Who typically decides curriculum changes *(TODO-VERIFY each)* | What KaushalSetu can do |
|---|---|---|
| ITI trade under CTS | Central process under DGT | Provide an evidence pack. Suggest institute-level add-on workshops or short courses if the rules allow *(TODO-VERIFY flexibility)*. |
| QP-based short course (e.g. under PMKVY) | The SSC that owns the QP, with approval under NCVET's processes | Provide evidence to the SSC. Suggest switching to a more suitable existing QP. |
| Polytechnic diploma | State technical board (e.g. MSBTE in Maharashtra) | Provide evidence. Suggest electives. |
| Institute's own short or add-on course | The institute, within applicable rules | The **fastest lever**: act now while the official revision is in progress. |

---

## 12. Employer validation

### What it is

Employers review our recommendations and say whether they are right **before** anyone acts on them.

### Why we need it

- **Data can be wrong.** Postings may be biased and our extraction may make mistakes. Employers see the ground reality.
- **Buy-in.** Employers who helped shape a course are more likely to hire from it.
- **Commitment.** A **pledge** ("we will take 10 apprentices if you add this module") turns an opinion into a commitment. It is the strongest possible signal.

### How it works

For each recommendation, an employer can:
- **Approve**, **Reject** or mark **Not needed**
- **Comment**, e.g. "also add earthing and lightning protection"
- **Pledge** hires or apprenticeships, with a number and a timeframe
- Later, **rate** the trainees they actually hired

### Rules

- **One employer is not enough.** Require several responses, ideally from a mix of small and large employers.
- **Watch for conflicts of interest.** For example, a single large employer pushing a course that only suits itself.
- **Record who validated what, and when** (see [Section 14](#14-evidence-and-provenance)).
- **Validation informs, it does not replace** the official approval described in Section 11.

---

## 13. Candidate guidance

### What it is

Helping a young person answer: **"Which course near me is most likely to lead to a good job?"**

### What the candidate sees

- The top course options near them, with **local** placement rate, typical salary range and demand trend
- **Career paths**, e.g. "Helper → EV charging technician → Senior EV technician", and what to learn for each step
- All of it in **English, Hindi or Marathi**, in simple language, working on a basic phone

### Illustrative conversation (fictional)

> **Candidate (Marathi):** "मी नाशिकमध्ये राहतो आणि बारावी पास आहे. नोकरी मिळण्यासाठी मी कोणता कोर्स करावा?"
> *(I live in Nashik and have passed 12th. Which course should I do to get a job?)*
>
> **KaushalSetu:** suggests 2–3 courses near Nashik. For each, it shows the local placement rate, the salary range, and why the course is recommended (e.g. rising EV-charger demand), with a clear note on how confident the data is.

### Principles

- **Honest:** show ranges and confidence levels. **Never promise a job.**
- **Local:** outcomes near the candidate matter more than national averages.
- **Private:** collect only what is needed, with **consent**. Explain why each piece of information is asked for. *(TODO-VERIFY DPDP Act obligations, including the rules for users under 18.)*
- **No pressure:** no manipulative design that pushes a particular course.

---

## 14. Evidence and provenance

### Definitions

- **Evidence:** the facts that support a claim or recommendation. *"Demand is rising"* is a claim. *"212 postings mention this skill this quarter, up from 88"* is evidence.
- **Provenance:** **where a piece of data came from**: its source, when it was collected, under what license, whether it is real or synthetic, and who entered or changed it.

### What we record for every piece of data (provenance)

| Field | Example |
|---|---|
| Source | "Public job dataset X", "Employer survey via Telegram", "DGT Electrician syllabus" |
| Source reference | A document name, dataset row ID or survey ID |
| Collected on | 12 Aug 2026 |
| License / terms note | "Open dataset, attribution required" *(TODO-VERIFY per source)* |
| Real or synthetic | Synthetic |

### What an evidence card looks like (illustrative)

> **Recommendation:** Add "EV charging installation and high-voltage safety" to the Electrician course at Example ITI A, Nashik
> - 📈 EV-charger skill mentioned in **110** postings this quarter, up from **40** *(synthetic data)*
> - 📝 **4** employer surveys list it as hard to find
> - 💬 Consultation quote: *"Freshers don't know high-voltage safety"*
> - 🏭 Hypothetical event: EV component facility announced in Nashik
> - ✅ Validated by **4 of 5** employers; **35** apprenticeships pledged
> - **Confidence:** Medium (3 independent source types)

### Why it matters

- **Trust:** officials act on recommendations they can check.
- **Debugging:** when a number looks wrong, provenance lets us trace it back.
- **Accountability:** an audit trail of who changed what.
- **Honesty:** we can always show judges which parts are real and which are synthetic.

---

## 15. Synthetic data and why we need it

### What it is

**Synthetic data** is realistic but **artificially generated** data. It is made by a program we write, following rules we define.

### Why we may need it

- Real placement records, seat data and survey responses are **not publicly available**, or are personal and private.
- We cannot collect months of real data in 3 weeks.
- We need data that **deliberately contains known patterns**, so we can test whether our system finds them.

### Our rules for synthetic data

1. **Always labelled.** Every synthetic record is marked synthetic in the database and shows a visible "synthetic" badge in the UI.
2. **Repeatable.** The generator produces the **same** data every time we run it, so demos and tests are stable.
3. **Realistic shapes.** Numbers should behave plausibly, e.g. salaries within sensible ranges.
4. **Planted patterns.** We deliberately hide patterns in the data, e.g. *"EV-charger demand rises in Nashik"* or *"one course is oversupplied in Kolhapur"*. If our system rediscovers them, that shows the logic works.
5. **Never presented as real findings.** In the pitch we say: *"On synthetic data containing a planted shortage, KaushalSetu detected it and produced this plan."* We do not say *"Nashik has a shortage of 220 EV technicians."*

### What stays real, where possible

District names and official district codes; real public syllabi and QPs (verified); real public job datasets (license checked).

---

## 16. Data vs metric vs signal vs recommendation vs validation

These five words are easy to confuse. Using them precisely will prevent many design mistakes.

| Word | Definition | Example | Produced by |
|---|---|---|---|
| **Data** | A raw recorded fact, not yet interpreted | "Posting #123: EV Charging Technician, Nashik, ₹15–18k, posted 12 Aug" | Sources (postings, surveys, records) |
| **Metric** | A number **calculated from data** using a defined formula | "EV-charger postings in Nashik this quarter = 110, growth = +175%" | Our calculations |
| **Signal** | A metric **interpreted** as an indication that something is changing. It is uncertain, and stronger when several agree. | "Demand for EV-charger skills in Nashik is rising (medium confidence)" | Our analysis, combining metrics |
| **Recommendation** | A **proposed action**, with evidence, priority and the person or body who should act | "Add an EV charging module to the Electrician course at Example ITI A" | Our recommendation logic |
| **Validation** | A **human confirmation or rejection** of a recommendation by people with ground knowledge | "4 of 5 employers approved; 35 apprenticeships pledged; SSC reviewer agreed" | Employers, SSC reviewers, officials |

And after validation comes the **outcome**: what actually happened (e.g. placement improved). The outcome becomes new **data**, and the loop starts again.

```
DATA → METRIC → SIGNAL → RECOMMENDATION → VALIDATION → ACTION → OUTCOME → (new DATA)
```

### Common mistakes to avoid

- Treating a **metric** as a **signal** without checking other sources ("110 postings, so there's a shortage!").
- Showing a **recommendation** without its **evidence**.
- Treating employer **validation** as official **approval**. They are different (see [Section 11](#11-curriculum-alignment)).

---

## 17. The complete KaushalSetu loop: the Nashik EV example

> ⚠️ **Everything in this walkthrough is hypothetical or synthetic.** Institute names, numbers, events and quotes are made up to explain the loop.

**1. Industry demand.** In one quarter, KaushalSetu receives:
- a hypothetical event: an EV component manufacturer announces a facility in Nashik, with 1,200 expected jobs over two years
- 110 job postings mentioning EV charger installation, up from 40 last quarter
- 14 employer survey responses reporting a need for about 180 technicians in the next 12 months
- a consultation note: *"Freshers don't know high-voltage safety."*

**2. Skills.** From all of this, the system extracts skills:
- *Install and commission EV charging equipment* (band 2)
- *Apply high-voltage safety procedures* (band 2)
- *Test and diagnose EV battery packs* (band 2–3)
- *Read electrical wiring diagrams* (band 2), which is already widely taught

**3. District demand.** It combines the signals into an estimate for Nashik over the next 12 months, e.g. about **350** openings across EV-related roles. Confidence is **medium**, because three independent source types agree. The hypothetical plant adds more demand **3–6 quarters later**, after a lag.

**4. Training supply.** It looks at relevant courses in Nashik:
- Example ITI A (Electrician)
- Example PMKVY Centre B (an EV-related short course)

Together they produce about **90** trained people a year for these roles.

**5. Gap.** The ratio is 90 ÷ 350 ≈ **0.26**, so the district is **undersupplied**. At skill level, *EV charger installation* is taught nowhere, and *high-voltage safety* is taught at only one of the two institutes.

**6. Course health.** The Electrician course at Example ITI A scores **58/100**.
- Placement: acceptable
- Coverage of in-demand skills: **low (0.35)**, so the course is flagged **OUTDATED**
- Demand trend: rising, so the course is worth fixing rather than cutting

**7. Curriculum recommendations.**
- **Add** a module on EV charging installation and high-voltage safety, linked to a relevant NOS *(TODO-VERIFY which one)*
- **Update** battery content to testing level
- Needs: 2 EV charger training units, safety kits, and **ToT** for 2 of the 4 trainers
- Since the ITI trade syllabus is set centrally, the **immediate** action is a short add-on course at the ITI and **more seats** at Example PMKVY Centre B. An **evidence pack** goes to the official revision process.
- The district officer sees all of this in the **draft district training plan**.

**8. Employer validation.** 5 local employers review the proposal. 4 approve; 1 comments *"add earthing and lightning protection"*; together they **pledge 35 apprenticeships**. An SSC reviewer checks that the module aligns with the relevant NOS. The recommendation moves to **approved** and is included in the district plan.

**9. Placement outcomes.** The next batch trains with the add-on module. The institute records outcomes: placement, salary, 6-month retention and employer ratings. For example, placement rises from 62% to 74% in this made-up scenario, and employers rate safety knowledge higher.

**10. Feedback.** KaushalSetu compares what it predicted with what happened:
- Signals that predicted well get more weight next time; weak ones get less. Any change is reviewed by a human.
- *EV charger installation* moves from "emerging" to "established".
- Coverage improves, so the course health score rises.
- A candidate in Nashik who asks the chatbot in Marathi *"which course should I do?"* is now shown the updated course, with its better local results.

The next quarter, the loop runs again with the new data.

---

## 18. Terms to understand before coding

Every team member should be able to explain each term below in one sentence. ✅ Tick them off as a team.

### Domain terms
| Term | One-line meaning |
|---|---|
| Skill | A specific, teachable, checkable ability that an employer recognises |
| Proficiency level / band | How deep someone's ability in a skill is |
| Job role | A job made up of many skills |
| QP / NOS | The official standard for a job role, and its units |
| Course / module | How training is organised, and one part of it |
| Demand / supply / gap | Need vs trained availability vs the difference |
| Course health score | A 0–100 summary of a course's relevance and results, always shown with its breakdown |
| Coverage | The share of important demanded skills a course teaches at the required level |
| Recommendation | A proposed action with evidence |
| Validation / pledge | Employer confirmation / employer commitment to hire or train |
| Placement / retention | Got a job / still in it after 6 months |
| Career path | A sequence of roles someone can progress through |

### Data terms
| Term | One-line meaning |
|---|---|
| Record / field | One row of data / one piece of information in it |
| Dataset | A collection of records from one source |
| Taxonomy | An organised list of categories (e.g. our list of skills) |
| Alias | An alternative name for the same thing |
| Normalisation | Converting messy variations into one standard form ("Nasik" → "Nashik") |
| Deduplication | Finding and merging repeated records |
| Provenance | Where a record came from and its history |
| Synthetic data | Artificial data generated by rules, clearly labelled |
| Time period / quarter | The time window a number refers to (e.g. July–September) |
| District code | An official, stable ID for a district (LGD code) |

### Analysis terms
| Term | One-line meaning |
|---|---|
| Count / share | How many / what fraction of the total |
| Growth rate | How much something changed compared with the previous period |
| Ratio | One number divided by another (e.g. supply ÷ demand) |
| Weighted score | Several numbers combined, each with a different importance |
| Median | The middle value, safer than the average when there are outliers |
| Confidence | How much we trust a number, based on the amount and variety of evidence |
| Forecast | An estimate of a future value, with a range |
| Leading indicator / lag | An early sign of change / the delay before the change happens |
| Bias | A systematic tilt in data (e.g. online postings over-representing big cities) |
| Threshold | A cut-off value that triggers a label (e.g. ratio > 1.5 = oversupplied) |

### AI / language-processing terms
| Term | One-line meaning |
|---|---|
| NLP | Natural Language Processing: getting computers to work with human language |
| Extraction | Pulling specific information (e.g. skills) out of free text |
| Embedding | Turning text into a list of numbers so that texts with similar meanings end up close together |
| Similarity | How close two embeddings are; used to match "PV fitting" to "solar installation" |
| LLM | Large Language Model: an AI model like ChatGPT that reads and writes text |
| Hallucination | When an AI confidently states something false |
| Human-in-the-loop | A person reviews AI output before it is used |
| Gold set | A small set of examples labelled correctly by humans, used to test the AI |
| Precision / recall | Of the skills the AI found, how many were right / of the real skills, how many the AI found |

### Platform terms
| Term | One-line meaning |
|---|---|
| Database | Organised storage for our data |
| API | A defined way for one program (e.g. the website) to ask another (the server) for data |
| Role-based access | Each user type sees and does only what their role allows |
| PII | Personally Identifiable Information (names, phone numbers, etc.) |
| Consent | A user's clear permission to use their data for a stated purpose |
| Audit log | A record of who did what, and when |
| DPDP Act, 2023 | India's personal data protection law *(TODO-VERIFY current rules)* |

### Quick self-check (discuss as a team)
1. Why can't we compare an ITI syllabus directly with a job posting?
2. Why are "110 postings" not the same as "110 jobs"?
3. What is the difference between a signal and a recommendation?
4. Why does an employer's approval not change an ITI trade syllabus by itself?
5. How will judges know which of our numbers are synthetic?

---

## 19. What must be officially verified, and where

**How to verify:** use the official website of the named body. Find it by searching the body's full name, and confirm it is on an official government domain (typically ending in `gov.in` or `nic.in`). Record the URL you opened, the date and the result in `data/research/source_inventory.csv` (see `docs/DATA_COLLECTION_PLAN.md`). URLs found by an automated check on 2026-09-29 are listed in [`DATA_SOURCE_INVENTORY.md`](DATA_SOURCE_INVENTORY.md). They still need a team member to confirm them.

| # | Item to verify | Why it matters | Where to verify | Owner | Done |
|---|---|---|---|---|---|
| 1 | Current NSQF level scale and level descriptors | We attach levels to skills, roles and courses | NCVET official website | | ☐ |
| 2 | NCVET's current functions | So we describe the approval process correctly | NCVET official website | | ☐ |
| 3 | QPs and NOS for our roles (solar PV, EV charging/service, electrician-type roles): codes, versions, validity, NSQF levels | Our Skill Graph is built on them; no guessed codes | National Qualification Register (NQR); the owning SSC's website | | ☐ |
| 4 | Which SSC owns which of our roles (Green Jobs, Automotive, Electronics, Power, …) | Routing evidence to the right reviewer | NQR; SSC websites; NSDC website | | ☐ |
| 5 | CTS trade syllabi for our trades (e.g. Electrician, Wireman, and any EV- or solar-related trades): duration, entry qualification, latest revision, equipment lists | Our main supply-side documents | DGT official website | | ☐ |
| 6 | How ITI curricula are revised, and what flexibility an institute has for add-on or short courses | Our recommendations must be realistic | DGT; Maharashtra DVET (TODO-VERIFY name) | | ☐ |
| 7 | Instructor training schemes (e.g. Craft Instructor Training Scheme) and ToT options | Trainer-development recommendations | DGT; relevant SSC websites | | ☐ |
| 8 | PMKVY: current phase, rules, course alignment to QPs, implementation structure, definition of "placement" | Short-course recommendations and outcome definitions | MSDE; Skill India Digital Hub; NSDC | | ☐ |
| 9 | Polytechnic regulation and curriculum authority in Maharashtra | Routing polytechnic recommendations | AICTE; MSBTE | | ☐ |
| 10 | NCO occupation codes (current edition) for our roles | Standard job-role identifiers | Ministry of Labour & Employment; NCS portal | | ☐ |
| 11 | NCS portal: data access options and terms of use | Possible job-posting source | National Career Service portal | | ☐ |
| 12 | District names and LGD codes for Pune, Nashik, Nagpur, Kolhapur | Stable district IDs | Local Government Directory (LGD) | | ☐ |
| 13 | District Skill Committee composition and the current District Skill Development Plan format; SANKALP status | Our district-plan output imitates it | MSDE; the Maharashtra state skill department (TODO-VERIFY name) | | ☐ |
| 14 | Whether PLFS estimates are reliable at district level | Whether we can use them for district demand | MoSPI (Ministry of Statistics & Programme Implementation) | | ☐ |
| 15 | Udyam / MSME data availability by district and sector | Sector growth signal | Ministry of MSME; Udyam portal; Open Government Data platform | | ☐ |
| 16 | Apprenticeship schemes applicable to ITI-level trainees | Employer pledges of apprenticeships | MSDE; DGT; the official apprenticeship portal | | ☐ |
| 17 | DPDP Act, 2023: current rules, consent requirements, rules for children | Candidate and employer data handling | MeitY (Ministry of Electronics & IT); official gazette | | ☐ |
| 18 | Licenses of any public job-posting datasets we use | Legal use of data | Each dataset's own page | | ☐ |
| 19 | License and currency of district boundary map files | The map in our dashboard | Source of the boundary file; cross-check names with LGD | | ☐ |
| 20 | Terms of use of any language AI service we use (e.g. Bhashini, if used) | Translation and voice features | The service's official website | | ☐ |
| 21 | Salary benchmarks or minimum wages, if we display them | Avoid misleading candidates | Maharashtra state labour department | | ☐ |
| 22 | Every statistic, name or claim used in the pitch deck | Credibility with judges | The original official source, cited on the slide | | ☐ |

> **Team rule:** until an item is verified, the product and the pitch must show it as a **placeholder** or clearly label it **illustrative**.

---

*Change log*
- v0.1: first draft of the domain primer for the team.
