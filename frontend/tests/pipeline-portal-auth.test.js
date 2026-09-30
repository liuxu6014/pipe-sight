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
  assert.equal(getDefaultLoginPath({ roles: ['admin'], permissions: [] }), '/system/role')
  assert.equal(getDefaultLoginPath({ roles: [], permissions: ['*:*:*'] }), '/system/role')
  assert.equal(getDefaultLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }), '/portal')
})

test('keeps post-login redirects on the surface that matches the signed-in identity', () => {
  assert.equal(typeof portalAuth.resolvePostLoginPath, 'function')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/index'), '/system/role')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/pipeline/dashboard'), '/system/role')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/portal/news'), '/system/role')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: [], permissions: ['*:*:*'] }, '/portal'), '/system/role')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }, '/pipeline/dashboard'), '/portal')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['ROLE_DEFAULT'], permissions: [] }, '/portal/news'), '/portal/news')
  assert.equal(portalAuth.resolvePostLoginPath({ roles: ['admin'], permissions: [] }, '/pipeline/report'), '/pipeline/report')
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
