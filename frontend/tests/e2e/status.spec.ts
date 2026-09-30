import { expect, test } from '@playwright/test'

const BACKEND_HEALTH_URL = 'http://127.0.0.1:8000/health'

test('the system status page loads', async ({ page }) => {
  await page.goto('/status')
  await expect(page.getByRole('heading', { level: 1, name: 'InnovProcure' })).toBeVisible()
  await expect(page.getByText('System status')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check again' })).toBeVisible()
})

test('status checks pass when backend and database are running', async ({ page, request }) => {
  // This test needs the backend (uvicorn) and the db container. Skip clearly if they are off.
  const backendUp = await request
    .get(BACKEND_HEALTH_URL, { timeout: 3_000 })
    .then((response) => response.ok())
    .catch(() => false)
  test.skip(!backendUp, `Backend not running at ${BACKEND_HEALTH_URL}; start it to run this test.`)

  await page.goto('/status')
  for (const id of ['status-api', 'status-db', 'status-pgvector']) {
    await expect(page.getByTestId(id).getByText('OK', { exact: true })).toBeVisible()
  }
  // The API reports which scoring configuration (config/scoring.yaml) it runs with.
  await expect(page.getByTestId('status-api')).toContainText(/scoring config v\d+/)
})
