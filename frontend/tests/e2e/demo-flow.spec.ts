import { expect, test } from '@playwright/test'

// The 5-minute demo path. Works with the backend running (live API + demo fallback for
// features without endpoints) and without it (offline demo data).
test('demo flow: dashboard -> Nashik -> course -> recommendation -> employer -> plan', async ({
  page,
}) => {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByRole('button', { name: /enter demo/i }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Maharashtra Skill Intelligence' }),
  ).toBeVisible()
  await expect(page.getByText('All figures come from a synthetic demo world')).toBeVisible()

  // Dashboard -> Nashik
  await page.getByRole('link', { name: /investigate nashik/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Nashik' })).toBeVisible()
  await expect(page.getByText('Industry → Training gap')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'EV Service Technician' })).toBeVisible()

  // Nashik -> EV Diagnostics skill
  await page
    .getByRole('link', { name: /EV Diagnostics/ })
    .first()
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'EV Diagnostics' })).toBeVisible()
  await expect(page.getByText('Not taught in Nashik').first()).toBeVisible()

  // Course health: 42/100 at risk
  await page.goto('/courses/nsk-iti-a-electrician')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Electrician (demo syllabus)' }),
  ).toBeVisible()
  const health = page.getByRole('region', { name: 'Course health score' })
  await expect(health).toContainText('42')
  await expect(health).toContainText(/at risk/i)
  await expect(page.getByText('Add an EV Diagnostics module').first()).toBeVisible()
  await expect(page.getByText('Priority 91').first()).toBeVisible()

  // Recommendation -> ask employers to validate
  await page
    .getByRole('button', { name: /ask employers to validate/i })
    .first()
    .click()
  await expect(page).toHaveURL(/\/employer$/)
  await page.getByText('Yes, I agree').click()
  await page.getByRole('button', { name: /submit validation/i }).click()
  await expect(page.getByText('your validation is recorded')).toBeVisible()

  // Pledge 35 apprenticeship seats
  await expect(page.getByLabel('Apprenticeship seats')).toHaveValue('35')
  await page.getByLabel(/I confirm/).check()
  await page.getByRole('button', { name: /pledge seats/i }).click()
  await expect(page.getByText('35 apprenticeship seats pledged')).toBeVisible()

  // District plan shows the pledge
  await page.goto('/district-plans')
  await expect(page.getByText('Nashik District Skill Plan 2026-27 (draft)')).toBeVisible()
  const seats = page.getByText('Apprenticeship seats pledged').first().locator('..').locator('..')
  await expect(seats).toContainText('35')
})

test('every main page renders without crashing', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(String(error)))
  await page.goto('/login')
  await page.getByRole('button', { name: /enter demo/i }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  for (const path of [
    '/districts',
    '/skills',
    '/courses',
    '/recommendations',
    '/employer',
    '/candidate',
    '/district-plans',
    '/admin',
    '/settings',
    '/help',
  ]) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  }
  expect(errors).toEqual([])
})
