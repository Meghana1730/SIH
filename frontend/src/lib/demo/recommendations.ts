// Curriculum and seat recommendations for the SYNTHETIC demo world. The backend has no
// recommendation engine yet, so these are written by hand from the analytics results of the
// demo run (numbers quoted in the evidence match /api/v1/analytics for the demo data).
// Priority scores are a demo heuristic (0-100), not an official ranking.

import type { EvidenceItem, Recommendation } from '@/lib/api/types'

const NSK = { code: 'MH-NASHIK', name: 'Nashik' }
const PUN = { code: 'MH-PUNE', name: 'Pune' }
const NGP = { code: 'MH-NAGPUR', name: 'Nagpur' }
const KOP = { code: 'MH-KOLHAPUR', name: 'Kolhapur' }

const ANALYTICS = 'analytics API, demo run (synthetic data)'

const NASHIK_EV_EVIDENCE: EvidenceItem[] = [
  {
    label: 'Job postings rising',
    detail: 'EV Service Technician postings in Nashik rose from 26 to 48 (last 2 quarters vs the 2 before).',
    kind: 'SYNTHETIC',
    source: ANALYTICS,
  },
  {
    label: 'Employers asking for more people',
    detail: 'Surveyed Nashik employers asked for 20 EV Service Technicians, up from 14 two quarters earlier.',
    kind: 'SYNTHETIC',
    source: ANALYTICS,
  },
  {
    label: 'Industry event (simulated)',
    detail: 'A simulated EV battery-pack assembly unit is expected to add about 180 EV Service Technician jobs in 2026Q4-2027Q3.',
    kind: 'SYNTHETIC',
    source: ANALYTICS,
  },
  {
    label: 'No local training supply',
    detail: 'No Nashik course trains EV Service Technicians: supply 0 against about 247 estimated openings a year (ratio 0.00, UNDER_SUPPLIED).',
    kind: 'SYNTHETIC',
    source: ANALYTICS,
  },
]

export const RECOMMENDATIONS: Recommendation[] = [
  {
    id: 'rec-nsk-ev-diagnostics',
    action: 'ADD_MODULE',
    title: 'Add an EV Diagnostics module',
    target: 'Electrician (demo syllabus), Example ITI A, Nashik',
    course_id: 'nsk-iti-a-electrician',
    district: NSK,
    sector: 'EV',
    priority_score: 91,
    priority: 'HIGH',
    reason:
      'EV Diagnostics is an EMERGING skill in Nashik job ads (27 mentions this quarter) and the course teaches none of it, while EV Service Technician demand in Nashik is 94.5/100 with no local EV course.',
    expected_impact:
      'About 49 completers a year would leave with an EV-ready module (80 h), creating a local pipeline for the Nashik EV shortage.',
    evidence: [
      {
        label: 'Skill trend',
        detail: 'EV Diagnostics mentions in Nashik job ads are EMERGING (demand score 89.3/100, 27 mentions in 2026Q3).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      ...NASHIK_EV_EVIDENCE,
      {
        label: 'Curriculum gap',
        detail: 'The course has no EV Diagnostics content; High-Voltage Safety is taught at basic level only.',
        kind: 'OBSERVED',
        source: 'course curriculum (demo syllabus)',
      },
    ],
    confidence: 'HIGH',
    status: 'NEW',
    employer_validations: 2,
    is_synthetic: true,
  },
  {
    id: 'rec-nsk-battery',
    action: 'ADD_MODULE',
    title: 'Add a Battery Management Systems module',
    target: 'Electrician (demo syllabus), Example ITI A, Nashik',
    course_id: 'nsk-iti-a-electrician',
    district: NSK,
    sector: 'EV',
    priority_score: 88,
    priority: 'HIGH',
    reason:
      'Battery Management is EMERGING in Nashik (demand 90.4/100, 28 mentions this quarter) and is not taught in any Nashik course.',
    expected_impact: 'Pairs with EV Diagnostics to cover the two most-requested EV service skills.',
    evidence: [
      {
        label: 'Skill trend',
        detail: 'Battery Management mentions in Nashik job ads are EMERGING (demand score 90.4/100).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      ...NASHIK_EV_EVIDENCE.slice(0, 2),
    ],
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 1,
    is_synthetic: true,
  },
  {
    id: 'rec-nsk-start-ev-course',
    action: 'START_COURSE',
    title: 'Start an EV Service Technician short course',
    target: 'Example Skill Centre C, Nashik',
    course_id: null,
    district: NSK,
    sector: 'EV',
    priority_score: 86,
    priority: 'HIGH',
    reason:
      'Nashik has the highest EV Service Technician demand in the four districts (94.5/100) and no EV course at all; Pune runs the same short course with an 84% placement rate.',
    expected_impact: 'A 40-seat batch (240 h) would add about 37 trained people a year at Pune-like completion.',
    evidence: [
      ...NASHIK_EV_EVIDENCE,
      {
        label: 'Comparable course',
        detail: 'EV Service Technician (demo short course) at Example EV Skills Centre E, Pune: 31 of 37 completers placed.',
        kind: 'SYNTHETIC',
        source: 'placement outcomes (synthetic)',
      },
    ],
    confidence: 'HIGH',
    status: 'NEW',
    employer_validations: 3,
    is_synthetic: true,
  },
  {
    id: 'rec-nsk-hv-safety',
    action: 'UPDATE_MODULE',
    title: 'Raise High-Voltage Safety from basic to advanced',
    target: 'Electrician (demo syllabus), Example ITI A, Nashik',
    course_id: 'nsk-iti-a-electrician',
    district: NSK,
    sector: 'EV',
    priority_score: 84,
    priority: 'HIGH',
    reason:
      'High-Voltage Safety is the most demanded skill in Nashik (91.5/100, EMERGING) but the Electrical Safety module only covers it at basic level.',
    expected_impact: 'Low-cost change inside an existing 40 h module; prerequisite for any EV work.',
    evidence: [
      {
        label: 'Skill trend',
        detail: 'High-Voltage Safety mentions in Nashik rose 13 -> 17 -> 23 -> 31 over four quarters (+80%): EMERGING.',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      {
        label: 'Curriculum',
        detail: 'Electrical Safety module (40 h) teaches High-Voltage Safety at band 1 (basic).',
        kind: 'OBSERVED',
        source: 'course curriculum (demo syllabus)',
      },
    ],
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 1,
    is_synthetic: true,
  },
  {
    id: 'rec-nsk-employer-partnership',
    action: 'EMPLOYER_PARTNERSHIP',
    title: 'Set up an EV apprenticeship partnership',
    target: 'Example EV Service Hub, Nashik + Example ITI A, Nashik',
    course_id: 'nsk-iti-a-electrician',
    district: NSK,
    sector: 'EV',
    priority_score: 80,
    priority: 'HIGH',
    reason:
      'Two surveyed Nashik employers are asking for EV Service Technicians; on-the-job apprenticeships close the gap faster than a new course.',
    expected_impact: 'Apprenticeship seats pledged by employers go straight into the Nashik district plan.',
    evidence: NASHIK_EV_EVIDENCE.slice(1, 3),
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 0,
    is_synthetic: true,
  },
  {
    id: 'rec-kop-wireman-seats',
    action: 'REDUCE_SEATS',
    title: 'Reduce Wireman seats from 80 to 60',
    target: 'Wireman (demo syllabus), Example ITI J, Kolhapur',
    course_id: 'kop-iti-j-wireman',
    district: KOP,
    sector: 'ELECTRICAL',
    priority_score: 78,
    priority: 'MEDIUM',
    reason:
      'Kolhapur trains about 119 wiremen a year against about 57 estimated openings (ratio 2.10, OVER_SUPPLIED); only 20 of 68 recent completers here were placed.',
    expected_impact: 'Frees about 20 seats a year for an under-supplied trade such as Solar PV installation.',
    evidence: [
      {
        label: 'Oversupply',
        detail: 'Wireman supply 119/yr vs about 57 estimated openings a year in Kolhapur: ratio 2.10, OVER_SUPPLIED.',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      {
        label: 'Low absorption',
        detail: '20 of 68 Wireman completers at Example ITI J were placed (29%).',
        kind: 'SYNTHETIC',
        source: 'placement outcomes (synthetic)',
      },
      {
        label: 'Openings estimate',
        detail: 'Openings = postings in the last 4 quarters / coverage factor 0.3: a modelling assumption, not an official statistic.',
        kind: 'ASSUMPTION',
        source: 'config/scoring.yaml demand.openings',
      },
    ],
    confidence: 'HIGH',
    status: 'NEW',
    employer_validations: 0,
    is_synthetic: true,
  },
  {
    id: 'rec-pun-charging-seats',
    action: 'INCREASE_SEATS',
    title: 'Increase EV Charger Installation seats from 30 to 45',
    target: 'EV Charger Installation (demo short course), Example EV Skills Centre E, Pune',
    course_id: 'pun-tc-e-charging',
    district: PUN,
    sector: 'EV',
    priority_score: 74,
    priority: 'MEDIUM',
    reason:
      'Pune trains about 28 EV charger installers a year against about 187 estimated openings (ratio 0.15, UNDER_SUPPLIED); every seat was filled and 22 of 28 completers were placed.',
    expected_impact: 'About 14 more trained installers a year at current completion.',
    evidence: [
      {
        label: 'Shortage',
        detail: 'EV Charger Installation Technician in Pune: supply 28/yr vs about 187 openings a year (ratio 0.15).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      {
        label: 'Full batches',
        detail: '30 of 30 seats filled in 2025-26; 22 of 28 completers placed.',
        kind: 'SYNTHETIC',
        source: 'enrolments and placements (synthetic)',
      },
    ],
    confidence: 'HIGH',
    status: 'NEW',
    employer_validations: 1,
    is_synthetic: true,
  },
  {
    id: 'rec-nsk-motor-rewinding',
    action: 'RETIRE_MODULE',
    title: 'Shorten the Motor Rewinding module (60 h to 20 h)',
    target: 'Electrician (demo syllabus), Example ITI A, Nashik',
    course_id: 'nsk-iti-a-electrician',
    district: NSK,
    sector: 'ELECTRICAL',
    priority_score: 72,
    priority: 'MEDIUM',
    reason:
      'Motor Rewinding demand is DECLINING in every demo district; the freed 40 hours can carry the new EV Diagnostics module.',
    expected_impact: 'Makes room for EV content without lengthening the course.',
    evidence: [
      {
        label: 'Skill trend',
        detail: 'Motor Rewinding mentions in Nashik job ads are DECLINING (demand score 23.1/100, 2 mentions in 2026Q3).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
      {
        label: 'Role demand',
        detail: 'Motor Rewinding Technician demand is the lowest of all roles in every district (4.2-10.4/100).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
    ],
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 0,
    is_synthetic: true,
  },
  {
    id: 'rec-kop-solar-course',
    action: 'START_COURSE',
    title: 'Start a Solar PV Installer short course',
    target: 'Example ITI J, Kolhapur',
    course_id: null,
    district: KOP,
    sector: 'SOLAR_PV',
    priority_score: 69,
    priority: 'MEDIUM',
    reason:
      'No Kolhapur course trains Solar PV Installers, against about 110 estimated openings a year; seats freed from Wireman can be reused.',
    expected_impact: 'A 20-seat batch would start closing the Kolhapur solar gap.',
    evidence: [
      {
        label: 'No local supply',
        detail: 'Solar PV Installer in Kolhapur: supply 0 vs about 110 estimated openings a year (UNDER_SUPPLIED).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
    ],
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 0,
    is_synthetic: true,
  },
  {
    id: 'rec-ngp-motor-rewinding',
    action: 'RETIRE_MODULE',
    title: 'Shorten the Motor Rewinding module',
    target: 'Electrician (demo syllabus), Example ITI G, Nagpur',
    course_id: 'ngp-iti-g-electrician',
    district: NGP,
    sector: 'ELECTRICAL',
    priority_score: 58,
    priority: 'LOW',
    reason: 'Motor Rewinding Technician demand in Nagpur is 4.2/100 and declining.',
    expected_impact: 'Frees 40 hours for Solar PV or cable-installation content.',
    evidence: [
      {
        label: 'Role demand',
        detail: 'Motor Rewinding Technician demand in Nagpur: 4.2/100 (the lowest role in the district).',
        kind: 'SYNTHETIC',
        source: ANALYTICS,
      },
    ],
    confidence: 'MEDIUM',
    status: 'NEW',
    employer_validations: 0,
    is_synthetic: true,
  },
]

export const KEY_RECOMMENDATION_ID = 'rec-nsk-ev-diagnostics'
