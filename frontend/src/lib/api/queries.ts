// TanStack Query hooks: the only way pages read or change data. Every query returns
// Sourced<T> ({ data, source: 'live' | 'demo', note }) so pages can badge demo data.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { adminApi } from '@/lib/api/adminApi'
import { analyticsApi } from '@/lib/api/analyticsApi'
import { candidateApi } from '@/lib/api/candidateApi'
import { ApiError } from '@/lib/api/client'
import { coursesApi } from '@/lib/api/coursesApi'
import { districtApi } from '@/lib/api/districtApi'
import { employerApi } from '@/lib/api/employerApi'
import { plansApi } from '@/lib/api/plansApi'
import { recommendationsApi } from '@/lib/api/recommendationsApi'
import { skillsApi } from '@/lib/api/skillsApi'
import type {
  AnalyticsFilters,
  ApprenticeshipPledge,
  EmployerDemandSubmission,
  RecommendationStatus,
  SupplyGroup,
} from '@/lib/api/types'

const STALE = 5 * 60 * 1000

function clean(filters: AnalyticsFilters): AnalyticsFilters {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== 'ALL'),
  )
}

// ---------------------------------------------------------------- analytics
export function useRoleDemand(filters: AnalyticsFilters = {}) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['analytics', 'demand', 'role', f],
    queryFn: () => analyticsApi.roleDemand(f),
    staleTime: STALE,
  })
}

export function useSkillDemand(filters: AnalyticsFilters = {}) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['analytics', 'demand', 'skill', f],
    queryFn: () => analyticsApi.skillDemand(f),
    staleTime: STALE,
  })
}

export function useRoleSupply(filters: AnalyticsFilters = {}) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['analytics', 'supply', 'role', f],
    queryFn: () => analyticsApi.roleSupply(f),
    staleTime: STALE,
  })
}

export function useSupplyBreakdown(
  groupBy: Exclude<SupplyGroup, 'role'>,
  filters: AnalyticsFilters = {},
) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['analytics', 'supply', groupBy, f],
    queryFn: () => analyticsApi.supplyBreakdown(groupBy, f),
    staleTime: STALE,
  })
}

export function useMismatch(filters: AnalyticsFilters = {}) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['analytics', 'mismatch', f],
    queryFn: () => analyticsApi.mismatch(f),
    staleTime: STALE,
  })
}

export function useDistrictMismatch(district: string | undefined, quarter?: string) {
  return useQuery({
    queryKey: ['analytics', 'district-mismatch', district, quarter ?? null],
    queryFn: () => analyticsApi.districtMismatch(district!, quarter),
    enabled: Boolean(district),
    staleTime: STALE,
  })
}

/** Mismatch summaries for several districts at once (dashboard map). */
export function useDistrictMismatches(districts: string[], quarter?: string) {
  return useQuery({
    queryKey: ['analytics', 'district-mismatch', 'many', districts, quarter ?? null],
    queryFn: async () => {
      const results = await Promise.all(
        districts.map((d) => analyticsApi.districtMismatch(d, quarter)),
      )
      return {
        data: results.map((r) => r.data),
        source: results.every((r) => r.source === 'live') ? ('live' as const) : ('demo' as const),
        note: results.find((r) => r.note)?.note,
      }
    },
    enabled: districts.length > 0,
    staleTime: STALE,
  })
}

export function useRoleHistory(district?: string) {
  return useQuery({
    queryKey: ['analytics', 'history', 'role', district ?? 'ALL'],
    queryFn: () => analyticsApi.roleHistory(district),
    staleTime: STALE,
  })
}

export function useSkillHistory(filters: { district?: string; skill?: string } = {}) {
  return useQuery({
    queryKey: ['analytics', 'history', 'skill', filters],
    queryFn: () => analyticsApi.skillHistory(filters),
    staleTime: STALE,
  })
}

export function useQuarters() {
  return useQuery({
    queryKey: ['analytics', 'quarters'],
    queryFn: analyticsApi.quarters,
    staleTime: Infinity,
  })
}

// ---------------------------------------------------------------- directory
export function useDistricts() {
  return useQuery({ queryKey: ['districts'], queryFn: districtApi.list, staleTime: STALE })
}

export function useInstitutes() {
  return useQuery({ queryKey: ['institutes'], queryFn: districtApi.institutes, staleTime: STALE })
}

// ---------------------------------------------------------------- skills / courses
export function useSkills(filters: { district?: string; quarter?: string } = {}) {
  const f = clean(filters)
  return useQuery({
    queryKey: ['skills', f],
    queryFn: () => skillsApi.list(f),
    staleTime: STALE,
  })
}

export function useSkillDetail(skill: string | undefined, quarter?: string) {
  return useQuery({
    queryKey: ['skills', 'detail', skill, quarter ?? null],
    queryFn: () => skillsApi.detail(skill!, quarter),
    enabled: Boolean(skill),
    staleTime: STALE,
  })
}

export function useCourses() {
  return useQuery({ queryKey: ['courses'], queryFn: coursesApi.list, staleTime: STALE })
}

export function useCourse(id: string | undefined) {
  return useQuery({
    queryKey: ['courses', id],
    queryFn: () => coursesApi.get(id!),
    enabled: Boolean(id),
    staleTime: STALE,
  })
}

// ---------------------------------------------------------------- recommendations
export function useRecommendations() {
  return useQuery({ queryKey: ['recommendations'], queryFn: recommendationsApi.list })
}

export function useRecommendation(id: string | undefined) {
  return useQuery({
    queryKey: ['recommendations', id],
    queryFn: () => recommendationsApi.get(id!),
    enabled: Boolean(id),
  })
}

export function useSetRecommendationStatus() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: RecommendationStatus }) =>
      recommendationsApi.setStatus(id, status),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['recommendations'] })
      client.invalidateQueries({ queryKey: ['plans'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
}

// ---------------------------------------------------------------- employer
export function useEmployers() {
  return useQuery({ queryKey: ['employers'], queryFn: employerApi.list, staleTime: Infinity })
}

export function useEmployerActivity() {
  return useQuery({ queryKey: ['employer', 'activity'], queryFn: employerApi.activity })
}

function useEmployerMutation<T>(fn: (input: T) => Promise<unknown>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['employer'] })
      client.invalidateQueries({ queryKey: ['recommendations'] })
      client.invalidateQueries({ queryKey: ['plans'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
}

export function useSubmitDemand() {
  return useEmployerMutation((input: EmployerDemandSubmission) => employerApi.submitDemand(input))
}

export function useValidateRecommendation() {
  return useEmployerMutation(
    (input: { recommendationId: string; agree: boolean; comment: string }) =>
      employerApi.validate(input.recommendationId, input.agree, input.comment),
  )
}

export function usePledge() {
  return useEmployerMutation((input: ApprenticeshipPledge) => employerApi.pledge(input))
}

// ---------------------------------------------------------------- candidate / plans
export function useCareerPaths(district: string) {
  return useQuery({
    queryKey: ['candidate', 'paths', district],
    queryFn: () => candidateApi.careerPaths(district),
    staleTime: STALE,
  })
}

export function usePlans() {
  return useQuery({ queryKey: ['plans'], queryFn: plansApi.list })
}

export function usePlan(district: string | undefined) {
  return useQuery({
    queryKey: ['plans', district],
    queryFn: () => plansApi.get(district!),
    enabled: Boolean(district),
  })
}

export function useSetPlanAction() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: string; status: 'PLANNED' | 'IN_PROGRESS' | 'DONE' }) =>
      plansApi.setActionStatus(input.id, input.status),
    onSuccess: () => client.invalidateQueries({ queryKey: ['plans'] }),
  })
}

export function useSubmitPlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: plansApi.submit,
    onSuccess: () => client.invalidateQueries({ queryKey: ['plans'] }),
  })
}

// ---------------------------------------------------------------- admin
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => adminApi.health(signal),
    retry: false,
  })
}

export function useDbHealth() {
  return useQuery({
    queryKey: ['health', 'db'],
    queryFn: ({ signal }) => adminApi.dbHealth(signal),
    retry: false,
  })
}

export function useUsers(enabled = true) {
  return useQuery({ queryKey: ['admin', 'users'], queryFn: adminApi.users, enabled, retry: false })
}

export function useAuditLog(enabled = true) {
  return useQuery({
    queryKey: ['admin', 'audit'],
    queryFn: () => adminApi.auditLog(),
    enabled,
    retry: false,
  })
}

export function useRunPipeline() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: adminApi.runPipeline,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['analytics'] })
      client.invalidateQueries({ queryKey: ['skills'] })
      client.invalidateQueries({ queryKey: ['courses'] })
      client.invalidateQueries({ queryKey: ['admin'] })
    },
  })
}

export function useResetDemo() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: adminApi.resetDemo,
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useSimulateEvExpansion() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (on: boolean) => adminApi.simulateEvExpansion(on),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
