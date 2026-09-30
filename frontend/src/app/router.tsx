import { lazy, Suspense, type ComponentType } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import type { RouteHandle } from '@/components/layout/route-meta'
import { LoadingState } from '@/components/states'
import { CURRICULA, OFFERINGS, SKILL_NAMES } from '@/lib/demo/catalog'
import { districtName } from '@/lib/format'

// Pages are loaded on demand so the first screen stays small.
function page(load: () => Promise<{ default: ComponentType }>) {
  const Page = lazy(load)
  return (
    <Suspense fallback={<LoadingState rows={4} />}>
      <Page />
    </Suspense>
  )
}

function courseCrumb(id: string | undefined): string {
  const offering = OFFERINGS.find((o) => o.id === id)
  return offering ? `${CURRICULA[offering.course].name}, ${offering.institute.name}` : 'Course'
}

const h = (handle: RouteHandle) => handle

export const router = createBrowserRouter([
  { path: '/login', element: page(() => import('@/pages/LoginPage')) },
  { path: '/status', element: page(() => import('@/pages/SystemStatusPage')) },
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      {
        path: 'dashboard',
        handle: h({ titleKey: 'pages.dashboard' }),
        element: page(() => import('@/pages/DashboardPage')),
      },
      {
        path: 'districts',
        handle: h({ titleKey: 'pages.districts', crumb: 'District Intelligence' }),
        children: [
          { index: true, element: page(() => import('@/pages/DistrictsPage')) },
          {
            path: ':district',
            handle: h({ crumb: (p) => districtName(p.district ?? '') }),
            element: page(() => import('@/pages/DistrictDetailPage')),
          },
        ],
      },
      {
        path: 'skills',
        handle: h({ titleKey: 'pages.skills', crumb: 'Skills' }),
        children: [
          { index: true, element: page(() => import('@/pages/SkillsPage')) },
          {
            path: ':skill',
            handle: h({ crumb: (p) => SKILL_NAMES[p.skill ?? ''] ?? p.skill ?? 'Skill' }),
            element: page(() => import('@/pages/SkillDetailPage')),
          },
        ],
      },
      {
        path: 'courses',
        handle: h({ titleKey: 'pages.courses', crumb: 'Course Health' }),
        children: [
          { index: true, element: page(() => import('@/pages/CoursesPage')) },
          {
            path: ':courseId',
            handle: h({ crumb: (p) => courseCrumb(p.courseId) }),
            element: page(() => import('@/pages/CourseDetailPage')),
          },
        ],
      },
      {
        path: 'recommendations/:recId?',
        handle: h({ titleKey: 'pages.recommendations', crumb: 'Recommendations' }),
        element: page(() => import('@/pages/RecommendationsPage')),
      },
      {
        path: 'employer',
        handle: h({ titleKey: 'pages.employer', crumb: 'Employer Portal' }),
        element: page(() => import('@/pages/EmployerPage')),
      },
      {
        path: 'candidate',
        handle: h({ titleKey: 'pages.candidate', crumb: 'Career Guidance' }),
        element: page(() => import('@/pages/CandidatePage')),
      },
      {
        path: 'district-plans',
        handle: h({ titleKey: 'pages.plans', crumb: 'District Plans' }),
        element: page(() => import('@/pages/DistrictPlansPage')),
      },
      {
        path: 'admin',
        handle: h({ titleKey: 'pages.admin', crumb: 'Demo Controls' }),
        element: page(() => import('@/pages/AdminPage')),
      },
      {
        path: 'settings',
        handle: h({ titleKey: 'pages.settings', crumb: 'Settings' }),
        element: page(() => import('@/pages/SettingsPage')),
      },
      {
        path: 'help',
        handle: h({ titleKey: 'pages.help', crumb: 'Help' }),
        element: page(() => import('@/pages/HelpPage')),
      },
      { path: '*', element: page(() => import('@/pages/NotFoundPage')) },
    ],
  },
])
