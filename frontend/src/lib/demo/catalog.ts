// Course catalogue of the SYNTHETIC demo world, copied from data/synthetic/spec/demo_world.yaml
// (curricula) and the synthetic 2025-26 offerings / placement outcomes in the dev database.
// The backend has no course endpoint yet, so the frontend keeps this copy. All of it is demo data.

import type { RoleRef, SectorCode } from '@/lib/api/types'

export type Module = { title: string; hours: number; skills: [code: string, band: number][] }

// `related` = sectors whose skills a course is judged against (a modelling assumption: ITI
// electricians are the usual feeder for EV service work; wiremen are not).
export const CURRICULA: Record<
  string,
  { name: string; sector: SectorCode; related: SectorCode[]; role: RoleRef; modules: Module[] }
> = {
  'demo-electrician': {
    name: 'Electrician (demo syllabus)',
    sector: 'ELECTRICAL',
    related: ['ELECTRICAL', 'EV'],
    role: { code: 'electrician', title: 'Electrician', sector: 'ELECTRICAL' },
    modules: [
      {
        title: 'Electrical Wiring',
        hours: 120,
        skills: [
          ['electrical-wiring', 3],
          ['electrical-testing', 1],
          ['earthing', 2],
          ['cable-installation', 1],
        ],
      },
      {
        title: 'Electrical Safety',
        hours: 40,
        skills: [
          ['electrical-safety', 3],
          ['hv-safety', 1],
        ],
      },
      { title: 'Basic Motors', hours: 60, skills: [['motor-maintenance', 2]] },
      { title: 'Motor Rewinding', hours: 60, skills: [['motor-rewinding', 3]] },
    ],
  },
  'demo-wireman': {
    name: 'Wireman (demo syllabus)',
    sector: 'ELECTRICAL',
    related: ['ELECTRICAL'],
    role: { code: 'wireman', title: 'Wireman', sector: 'ELECTRICAL' },
    modules: [
      {
        title: 'Domestic Wiring Practice',
        hours: 100,
        skills: [
          ['electrical-wiring', 2],
          ['earthing', 2],
        ],
      },
      { title: 'Cable Laying and Jointing', hours: 50, skills: [['cable-installation', 2]] },
      { title: 'Electrical Safety Basics', hours: 30, skills: [['electrical-safety', 2]] },
    ],
  },
  'demo-ev-technician': {
    name: 'EV Service Technician (demo short course)',
    sector: 'EV',
    related: ['EV', 'ELECTRICAL'],
    role: { code: 'ev-service-technician', title: 'EV Service Technician', sector: 'EV' },
    modules: [
      {
        title: 'High-Voltage Safety for EVs',
        hours: 30,
        skills: [
          ['electrical-safety', 2],
          ['hv-safety', 3],
        ],
      },
      {
        title: 'EV Diagnostics',
        hours: 80,
        skills: [
          ['electrical-testing', 2],
          ['ev-diagnostics', 3],
        ],
      },
      { title: 'Battery Management Systems', hours: 60, skills: [['battery-management', 3]] },
      { title: 'EV Motor and Controller Basics', hours: 50, skills: [['ev-motor-controller', 2]] },
      { title: 'Customer Handling', hours: 20, skills: [['customer-communication', 2]] },
    ],
  },
  'demo-ev-charging': {
    name: 'EV Charger Installation (demo short course)',
    sector: 'EV',
    related: ['EV', 'ELECTRICAL'],
    role: {
      code: 'ev-charging-installer',
      title: 'EV Charger Installation Technician',
      sector: 'EV',
    },
    modules: [
      { title: 'EV Charging Systems', hours: 60, skills: [['ev-charging-systems', 3]] },
      {
        title: 'Wiring and Earthing for Chargers',
        hours: 40,
        skills: [
          ['electrical-wiring', 2],
          ['earthing', 2],
          ['cable-installation', 2],
        ],
      },
      {
        title: 'Safety and Testing',
        hours: 30,
        skills: [
          ['electrical-safety', 2],
          ['electrical-testing', 2],
          ['hv-safety', 2],
        ],
      },
    ],
  },
  'demo-solar-pv': {
    name: 'Solar PV Installer (demo short course)',
    sector: 'SOLAR_PV',
    related: ['SOLAR_PV', 'ELECTRICAL'],
    role: { code: 'solar-pv-installer', title: 'Solar PV Installer', sector: 'SOLAR_PV' },
    modules: [
      { title: 'Site Survey', hours: 20, skills: [['solar-site-survey', 2]] },
      {
        title: 'PV Installation',
        hours: 80,
        skills: [
          ['work-at-height', 2],
          ['solar-pv-installation', 3],
        ],
      },
      {
        title: 'Inverters and Commissioning',
        hours: 50,
        skills: [
          ['electrical-testing', 2],
          ['solar-inverter-maintenance', 2],
        ],
      },
      { title: 'Electrical Safety on Site', hours: 30, skills: [['electrical-safety', 2]] },
    ],
  },
}

export const SKILL_NAMES: Record<string, string> = {
  'battery-management': 'Battery Management',
  'cable-installation': 'Cable Laying and Termination',
  'customer-communication': 'Customer Communication',
  earthing: 'Earthing and Grounding',
  'electrical-safety': 'Electrical Safety',
  'electrical-testing': 'Electrical Testing and Measurement',
  'electrical-wiring': 'Electrical Wiring',
  'ev-charging-systems': 'EV Charging Systems',
  'ev-diagnostics': 'EV Diagnostics',
  'ev-motor-controller': 'EV Motor and Controller Servicing',
  'hv-safety': 'High-Voltage Safety',
  'motor-maintenance': 'Basic Motor Maintenance',
  'motor-rewinding': 'Motor Rewinding',
  'panel-wiring': 'Control Panel Wiring',
  'solar-inverter-maintenance': 'Solar Inverter Servicing',
  'solar-pv-installation': 'Solar PV Installation',
  'solar-site-survey': 'Solar Site Survey',
  'work-at-height': 'Working at Height Safety',
}

export const SKILL_SECTOR: Record<string, SectorCode> = {
  'battery-management': 'EV',
  'ev-charging-systems': 'EV',
  'ev-diagnostics': 'EV',
  'ev-motor-controller': 'EV',
  'hv-safety': 'EV',
  'solar-inverter-maintenance': 'SOLAR_PV',
  'solar-pv-installation': 'SOLAR_PV',
  'solar-site-survey': 'SOLAR_PV',
  'work-at-height': 'SOLAR_PV',
}

export function skillSector(code: string): SectorCode {
  return SKILL_SECTOR[code] ?? 'ELECTRICAL'
}

/** 2025-26 offerings: seats, completion and placements from the synthetic dev database. */
export type OfferingRecord = {
  id: string
  course: keyof typeof CURRICULA
  institute: { code: string; name: string }
  district: { code: string; name: string }
  seats: number
  seats_filled: number
  completed: number
  placed: number
}

const NSK = { code: 'MH-NASHIK', name: 'Nashik' }
const PUN = { code: 'MH-PUNE', name: 'Pune' }
const NGP = { code: 'MH-NAGPUR', name: 'Nagpur' }
const KOP = { code: 'MH-KOLHAPUR', name: 'Kolhapur' }

export const OFFERINGS: OfferingRecord[] = [
  {
    id: 'nsk-iti-a-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-A', name: 'Example ITI A, Nashik' },
    district: NSK,
    seats: 60,
    seats_filled: 57,
    completed: 49,
    placed: 25,
  },
  {
    id: 'nsk-iti-b-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-B', name: 'Example ITI B, Nashik' },
    district: NSK,
    seats: 40,
    seats_filled: 35,
    completed: 30,
    placed: 16,
  },
  {
    id: 'nsk-iti-a-wireman',
    course: 'demo-wireman',
    institute: { code: 'EX-ITI-A', name: 'Example ITI A, Nashik' },
    district: NSK,
    seats: 60,
    seats_filled: 52,
    completed: 44,
    placed: 20,
  },
  {
    id: 'nsk-tc-c-solar',
    course: 'demo-solar-pv',
    institute: { code: 'EX-TC-C', name: 'Example Skill Centre C, Nashik' },
    district: NSK,
    seats: 60,
    seats_filled: 55,
    completed: 50,
    placed: 33,
  },
  {
    id: 'pun-iti-d-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-D', name: 'Example ITI D, Pune' },
    district: PUN,
    seats: 60,
    seats_filled: 58,
    completed: 52,
    placed: 32,
  },
  {
    id: 'pun-iti-d-wireman',
    course: 'demo-wireman',
    institute: { code: 'EX-ITI-D', name: 'Example ITI D, Pune' },
    district: PUN,
    seats: 60,
    seats_filled: 52,
    completed: 47,
    placed: 24,
  },
  {
    id: 'pun-tc-e-ev',
    course: 'demo-ev-technician',
    institute: { code: 'EX-TC-E', name: 'Example EV Skills Centre E, Pune' },
    district: PUN,
    seats: 40,
    seats_filled: 40,
    completed: 37,
    placed: 31,
  },
  {
    id: 'pun-tc-e-charging',
    course: 'demo-ev-charging',
    institute: { code: 'EX-TC-E', name: 'Example EV Skills Centre E, Pune' },
    district: PUN,
    seats: 30,
    seats_filled: 30,
    completed: 28,
    placed: 22,
  },
  {
    id: 'pun-iti-f-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-F', name: 'Example ITI F, Pune' },
    district: PUN,
    seats: 40,
    seats_filled: 38,
    completed: 33,
    placed: 20,
  },
  {
    id: 'pun-iti-f-solar',
    course: 'demo-solar-pv',
    institute: { code: 'EX-ITI-F', name: 'Example ITI F, Pune' },
    district: PUN,
    seats: 60,
    seats_filled: 54,
    completed: 49,
    placed: 33,
  },
  {
    id: 'ngp-iti-g-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-G', name: 'Example ITI G, Nagpur' },
    district: NGP,
    seats: 60,
    seats_filled: 56,
    completed: 49,
    placed: 27,
  },
  {
    id: 'ngp-iti-g-wireman',
    course: 'demo-wireman',
    institute: { code: 'EX-ITI-G', name: 'Example ITI G, Nagpur' },
    district: NGP,
    seats: 60,
    seats_filled: 54,
    completed: 46,
    placed: 22,
  },
  {
    id: 'ngp-tc-h-charging',
    course: 'demo-ev-charging',
    institute: { code: 'EX-TC-H', name: 'Example Training Centre H, Nagpur' },
    district: NGP,
    seats: 30,
    seats_filled: 26,
    completed: 24,
    placed: 17,
  },
  {
    id: 'ngp-tc-h-solar',
    course: 'demo-solar-pv',
    institute: { code: 'EX-TC-H', name: 'Example Training Centre H, Nagpur' },
    district: NGP,
    seats: 60,
    seats_filled: 56,
    completed: 50,
    placed: 33,
  },
  {
    id: 'kop-iti-j-electrician',
    course: 'demo-electrician',
    institute: { code: 'EX-ITI-J', name: 'Example ITI J, Kolhapur' },
    district: KOP,
    seats: 40,
    seats_filled: 35,
    completed: 30,
    placed: 15,
  },
  {
    id: 'kop-iti-j-wireman',
    course: 'demo-wireman',
    institute: { code: 'EX-ITI-J', name: 'Example ITI J, Kolhapur' },
    district: KOP,
    seats: 80,
    seats_filled: 76,
    completed: 68,
    placed: 20,
  },
  {
    id: 'kop-iti-k-wireman',
    course: 'demo-wireman',
    institute: { code: 'EX-ITI-K', name: 'Example ITI K, Kolhapur' },
    district: KOP,
    seats: 60,
    seats_filled: 57,
    completed: 51,
    placed: 14,
  },
]

export const DISTRICTS = [NSK, PUN, NGP, KOP]

export const ROLES: RoleRef[] = [
  { code: 'electrician', title: 'Electrician', sector: 'ELECTRICAL' },
  { code: 'wireman', title: 'Wireman', sector: 'ELECTRICAL' },
  { code: 'motor-rewinder', title: 'Motor Rewinding Technician', sector: 'ELECTRICAL' },
  { code: 'ev-service-technician', title: 'EV Service Technician', sector: 'EV' },
  { code: 'ev-charging-installer', title: 'EV Charger Installation Technician', sector: 'EV' },
  { code: 'solar-pv-installer', title: 'Solar PV Installer', sector: 'SOLAR_PV' },
  { code: 'solar-service-technician', title: 'Solar PV Service Technician', sector: 'SOLAR_PV' },
]
