// Demo-mode switches (frontend/.env.local; see README).
//
// VITE_DEMO_FALLBACK=false  turns the deterministic demo fallback OFF: pages then show the
//                           API error instead of demo data.
// VITE_DEMO_EMAIL / VITE_DEMO_PASSWORD  optional: lets "Enter demo" sign in to the local API
//                           with a demo account (python -m app.cli.demo_users). Never commit them.

export const DEMO_FALLBACK_ENABLED = import.meta.env.VITE_DEMO_FALLBACK !== 'false'

export const DEMO_LOGIN = {
  email: (import.meta.env.VITE_DEMO_EMAIL as string | undefined) ?? '',
  password: (import.meta.env.VITE_DEMO_PASSWORD as string | undefined) ?? '',
}

export const DEMO_ACCOUNTS = [
  { email: 'admin@kaushalsetu.example', role: 'admin', label: 'Platform admin' },
  { email: 'state@kaushalsetu.example', role: 'state_officer', label: 'State officer, Maharashtra' },
  { email: 'nashik@kaushalsetu.example', role: 'district_officer', label: 'District officer, Nashik' },
  { email: 'institute@kaushalsetu.example', role: 'institute_admin', label: 'Principal, Example ITI A' },
  { email: 'employer@kaushalsetu.example', role: 'employer', label: 'HR, Example EV Service Hub' },
  { email: 'candidate@kaushalsetu.example', role: 'candidate', label: 'Candidate' },
] as const
