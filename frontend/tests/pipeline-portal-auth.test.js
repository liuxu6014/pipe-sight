import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import * as portalAuth from '../src/utils/portal/auth.js'
import {
  getDefaultLoginPath,
  getLoginRedirect,
  isPortalLoginPath,
  isPortalProtectedPath,
  isPublicAuthPath,
  USER_PORTAL_LOGIN_PATH
} from '../src/utils/portal/auth.js'

const managementRolePath = new URL('../src/views/system/role/index.vue', import.meta.url)
const loginPagePath = new URL('../src/views/login.vue', import.meta.url)

test('requires authentication for every user portal content route', () => {
  const protectedPaths = [
    '/portal',
    '/portal/news',
    '/portal/news/news-001',
    '/portal/papers',
    '/portal/papers/doc-001',
    '/portal/reports',
    '/portal/reports/report-001'
  ]

  for (const path of protectedPaths) {
    assert.equal(isPortalProtectedPath(path), true, `${path} should require user portal authentication`)
    assert.equal(isPublicAuthPath(path), false, `${path} must not be a public route`)
  }
})

test('ordinary users cannot enter management surfaces, even through a typed URL', () => {
  const user = { roles: ['common'], permissions: [] }
  for (const path of ['/pipeline/dashboard', '/pipeline/filter', '/system/user', '/monitor/server']) {
    assert.equal(portalAuth.canAccessApplicationPath(user, path), false)
  }
  for (const path of ['/portal', '/portal/me/tasks', '/user/profile/resetPwd']) {
    assert.equal(portalAuth.canAccessApplicationPath(user, path), true)
  }
  assert.equal(portalAuth.canAccessApplicationPath({ roles: ['admin'] }, '/pipeline/dashboard'), true)
})

test('keeps the legacy portal login path public only as a compatibility redirect', () => {
  assert.equal(USER_PORTAL_LOGIN_PATH, '/portal-login')
  assert.equal(isPortalLoginPath('/portal-login'), true)
  assert.equal(isPublicAuthPath('/login'), true)
  assert.equal(isPublicAuthPath('/portal-login'), true)
  assert.equal(isPortalProtectedPath('/portal-login'), false)
})

test('redirects anonymous user portal requests to the unified login with the original target', () => {
  assert.equal(getLoginRedirect('/portal'), '/login?redirect=%2Fportal')
  assert.equal(getLoginRedirect('/portal/news/news-001'), '/login?redirect=%2Fportal%2Fnews%2Fnews-001')
  assert.equal(getLoginRedirect('/portal/papers/doc-001?tab=ai'), '/login?redirect=%2Fportal%2Fpapers%2Fdoc-001%3Ftab%3Dai')
})

test('routes signed-in accounts to the right default surface by identity', () => {
  assert.equal(existsSync(managementRolePath), true)
  assert.equal(getDefaultLoginPath({ roles: ['admin'], permissions: [] }), '/pipeline/dashboard')
  assert.equal(getDefaultLoginPath({ roles: [], permissions: ['*:*:*'] }), '/pipeline/dashboard')
  assert.equal(getDefaultLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }), '/portal')
})

test('keeps post-login redirects on the surface that matches the signed-in identity', () => {
  assert.equal(typeof portalAuth.resolvePostLoginPath, 'function')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/index'), '/pipeline/dashboard')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/pipeline/dashboard'), '/pipeline/dashboard')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/portal/news'), '/portal/news')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: [], permissions: ['*:*:*'] }, '/portal'), '/portal')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }, '/pipeline/dashboard'), '/portal')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }, '/portal/news'), '/portal/news')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/pipeline/report'), '/pipeline/report')
})

test('preserves report deep links and rejects external login redirects', () => {
  const reportPath = '/portal/research/reports/report-sample?tab=versions'
  for (const user of [{ roles: ['admin'] }, { roles: ['ROLE_DEFAULT'] }]) {
    assert.equal(portalAuth.resolvePostLoginPath(user, reportPath), reportPath)
    for (const unsafe of ['https://example.com', '//example.com', '/\\example.com', ['/portal']]) {
      assert.equal(portalAuth.resolvePostLoginPath(user, unsafe), getDefaultLoginPath(user))
    }
  }
})

test('remembers only the account name and clears legacy password cookies', async () => {
  const loginPage = await import('node:fs/promises').then(fs => fs.readFile(loginPagePath, 'utf8'))

  assert.match(loginPage, /记住账号/)
  assert.match(loginPage, /Cookies\.remove\('password'\)/)
  assert.match(loginPage, /Cookies\.get\('rememberMe'\) === 'true'/)
  assert.doesNotMatch(loginPage, /Cookies\.set\('password'/)
  assert.doesNotMatch(loginPage, /from '@\/utils\/jsencrypt'/)
})

test('keeps keyboard focus inside the login dialog and restores it after closing', async () => {
  const loginPage = await import('node:fs/promises').then(fs => fs.readFile(loginPagePath, 'utf8'))

  assert.match(loginPage, /@keydown="handleDialogKeydown"/)
  assert.match(loginPage, /loginTrigger\.value = document\.activeElement/)
  assert.match(loginPage, /loginCardRef\.value\.querySelectorAll/)
  assert.match(loginPage, /nextTick\(\(\) => loginTrigger\.value\?\.focus\?\.\(\)\)/)
  assert.match(loginPage, /aria-label="刷新验证码"/)
})

test('declares the captcha image as PNG to match the backend renderer', async () => {
  const loginPage = await import('node:fs/promises').then(fs => fs.readFile(loginPagePath, 'utf8'))

  assert.match(loginPage, /data:image\/png;base64,' \+ res\.img/)
  assert.doesNotMatch(loginPage, /data:image\/gif;base64,' \+ res\.img/)
  assert.match(loginPage, /class="calm-code-error"/)
  assert.match(loginPage, /captchaEnabled\.value = true/)
  assert.match(loginPage, /function handleCodeImageError\(\)/)
})
