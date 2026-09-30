import {
  Building2,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LifeBuoy,
  Lightbulb,
  Map,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'

export type NavItem = { to: string; labelKey: string; icon: LucideIcon }

export const MAIN_NAV: NavItem[] = [
  { to: '/dashboard', labelKey: 'nav.overview', icon: LayoutDashboard },
  { to: '/districts', labelKey: 'nav.districts', icon: Map },
  { to: '/skills', labelKey: 'nav.skills', icon: Sparkles },
  { to: '/courses', labelKey: 'nav.courses', icon: GraduationCap },
  { to: '/recommendations', labelKey: 'nav.recommendations', icon: Lightbulb },
  { to: '/employer', labelKey: 'nav.employers', icon: Building2 },
  { to: '/candidate', labelKey: 'nav.candidates', icon: Users },
  { to: '/district-plans', labelKey: 'nav.plans', icon: FileText },
]

export const FOOTER_NAV: NavItem[] = [
  { to: '/admin', labelKey: 'nav.admin', icon: SlidersHorizontal },
  { to: '/settings', labelKey: 'nav.settings', icon: Settings },
  { to: '/help', labelKey: 'nav.help', icon: LifeBuoy },
]
