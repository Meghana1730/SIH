// Employers, the Nashik district plan and notifications of the SYNTHETIC demo world.
// Employer names are the demo world's "Example ..." records, not real companies.

import type { DistrictPlan, Employer, Notification } from '@/lib/api/types'

const NSK = { code: 'MH-NASHIK', name: 'Nashik' }
const PUN = { code: 'MH-PUNE', name: 'Pune' }
const NGP = { code: 'MH-NAGPUR', name: 'Nagpur' }
const KOP = { code: 'MH-KOLHAPUR', name: 'Kolhapur' }

export const EMPLOYERS: Employer[] = [
  { code: 'EX-EMP-NSK-01', name: 'Example EV Service Hub, Nashik', district: NSK, size: 'SMALL', sector: 'EV', is_synthetic: true },
  { code: 'EX-EMP-NSK-03', name: 'Example Charge Point Services, Nashik', district: NSK, size: 'SMALL', sector: 'EV', is_synthetic: true },
  { code: 'EX-EMP-NSK-02', name: 'Example Auto Components Unit, Nashik', district: NSK, size: 'MEDIUM', sector: 'ELECTRICAL', is_synthetic: true },
  { code: 'EX-EMP-NSK-04', name: 'Example Electricals and Contractors, Nashik', district: NSK, size: 'SMALL', sector: 'ELECTRICAL', is_synthetic: true },
  { code: 'EX-EMP-NSK-06', name: 'Example Solar Rooftops, Nashik', district: NSK, size: 'SMALL', sector: 'SOLAR_PV', is_synthetic: true },
  { code: 'EX-EMP-PUN-01', name: 'Example EV Workshop, Pune', district: PUN, size: 'SMALL', sector: 'EV', is_synthetic: true },
  { code: 'EX-EMP-PUN-02', name: 'Example Charging Networks, Pune', district: PUN, size: 'MEDIUM', sector: 'EV', is_synthetic: true },
  { code: 'EX-EMP-NGP-02', name: 'Example Solar EPC, Nagpur', district: NGP, size: 'SMALL', sector: 'SOLAR_PV', is_synthetic: true },
  { code: 'EX-EMP-KOP-01', name: 'Example Wiring Contractors, Kolhapur', district: KOP, size: 'SMALL', sector: 'ELECTRICAL', is_synthetic: true },
]

export const DEMO_EMPLOYER_CODE = 'EX-EMP-NSK-01'

export const NASHIK_PLAN: DistrictPlan = {
  id: 'plan-nashik-2026-27',
  district: NSK,
  title: 'Nashik District Skill Plan 2026-27 (draft)',
  period: '2026Q4 - 2027Q3',
  status: 'DRAFT',
  summary:
    'Nashik shows the sharpest EV skill shortage of the four demo districts: EV Service Technician demand is 94.5/100, no local course trains for it, and a simulated EV battery-pack unit is expected to add about 180 jobs for this role. The plan re-tools the existing Electrician course, starts a short EV course and uses employer apprenticeships to close the gap while new batches train.',
  priorities: [
    {
      title: 'Close the EV service gap',
      detail: 'Add EV Diagnostics and Battery Management to the Electrician course at Example ITI A; start an EV short course at Example Skill Centre C.',
      metric: 'EV Service Technician supply: 0 -> about 37 a year',
    },
    {
      title: 'Employer-backed apprenticeships',
      detail: 'Convert employer demand into apprenticeship seats linked to the re-tooled course.',
      metric: 'Apprenticeship seats pledged by employers',
    },
    {
      title: 'Retire declining content',
      detail: 'Shorten Motor Rewinding (declining in every district) to make room for EV modules without lengthening the course.',
      metric: '40 course hours re-used',
    },
  ],
  actions: [
    { id: 'act-1', title: 'Approve EV Diagnostics module for Electrician, Example ITI A', owner: 'Principal, Example ITI A', due: '2026-11-30', status: 'IN_PROGRESS', linked_recommendation: 'rec-nsk-ev-diagnostics' },
    { id: 'act-2', title: 'Employer validation of the EV module content', owner: 'District Skill Committee', due: '2026-10-31', status: 'PLANNED', linked_recommendation: 'rec-nsk-ev-diagnostics' },
    { id: 'act-3', title: 'Sign apprenticeship agreements with EV employers', owner: 'District Skill Committee', due: '2026-12-15', status: 'PLANNED', linked_recommendation: 'rec-nsk-employer-partnership' },
    { id: 'act-4', title: 'Start EV Service Technician short course (40 seats)', owner: 'Example Skill Centre C', due: '2027-01-15', status: 'PLANNED', linked_recommendation: 'rec-nsk-start-ev-course' },
    { id: 'act-5', title: 'Shorten Motor Rewinding module to 20 h', owner: 'Principal, Example ITI A', due: '2027-03-31', status: 'PLANNED', linked_recommendation: 'rec-nsk-motor-rewinding' },
  ],
  commitments: [
    { label: 'Courses re-tooled', value: '1' },
    { label: 'New short courses', value: '1' },
  ],
  prepared_by: 'Demo District Officer, Nashik',
  updated_at: '2026-09-28',
  is_synthetic: true,
}

export const NOTIFICATIONS: Notification[] = [
  {
    id: 'n-1',
    title: 'Nashik EV shortage flagged',
    body: 'EV Service Technician: supply 0 vs about 247 openings a year (UNDER_SUPPLIED, high confidence).',
    at: '2026-09-30',
    href: '/districts/MH-NASHIK',
    tone: 'danger',
  },
  {
    id: 'n-2',
    title: 'Course at risk',
    body: 'Electrician (demo syllabus), Example ITI A, Nashik scored 42/100.',
    at: '2026-09-30',
    href: '/courses/nsk-iti-a-electrician',
    tone: 'warning',
  },
  {
    id: 'n-3',
    title: 'Kolhapur Wireman oversupply',
    body: 'Supply is 2.1 times the estimated openings; 29% of recent completers placed.',
    at: '2026-09-29',
    href: '/districts/MH-KOLHAPUR',
    tone: 'warning',
  },
]
