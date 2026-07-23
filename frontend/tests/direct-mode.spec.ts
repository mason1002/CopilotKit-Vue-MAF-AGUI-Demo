import { expect, test } from '@playwright/test'

test('Vue calls the Agent endpoint directly', async ({ page }) => {
  const requestedUrls: string[] = []
  page.on('request', (request) => requestedUrls.push(request.url()))
  await page.goto('/?scoutTheme=light')
  await expect(page.getByText('Service online')).toBeVisible()
  await expect(page.locator('.flow-node')).toHaveCount(3)

  const responsePromise = page.waitForResponse(
    (response) => response.url() === 'http://127.0.0.1:8110/agent',
  )
  await page.getByRole('textbox', { name: 'Type a message...' }).fill('direct integration test')
  await page.getByRole('button', { name: 'Send message' }).click()
  const response = await responsePromise

  expect(response.status()).toBe(200)
  expect(response.url()).toBe('http://127.0.0.1:8110/agent')
  expect(response.request().method()).toBe('POST')
  await expect(page.locator('.route-state')).toHaveText(/complete/i)
  await expect(page.getByText('RUN_FINISHED')).toBeVisible()
  await expect(page.getByText(/directly from Vue/)).toBeVisible()
  await expect(page.getByText('Intermediary service')).toBeVisible()
  await expect(page.getByText('Agent Framework AG-UI')).toBeVisible()
  await expect(page.locator('.run-facts')).not.toContainText('REQUEST ID\n—')
  expect(requestedUrls.some((url) => new URL(url).pathname.startsWith('/copilotkit'))).toBe(false)

})

test('Direct desktop layout stays inside one viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1255, height: 767 })
  await page.goto('/?scoutTheme=light')

  const layout = await page.evaluate(() => ({
    horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    chatVisible: Boolean(document.querySelector('.chat-panel')),
  }))

  expect(layout.horizontalOverflow).toBe(0)
  expect(layout.chatVisible).toBe(true)
})