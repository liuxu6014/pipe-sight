import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { createMemoryHistory, createRouter } from 'vue-router'

function loginFlow({ menuFailure = false, loginFailure = false, target = '/portal/research/reports/sample' } = {}) {
  const source = readFileSync(new URL('../src/views/login.vue', import.meta.url), 'utf8')
  const actions = source.slice(source.indexOf('function handleLogin()'), source.indexOf('function getCode()'))
  const calls = { login: 0, info: 0, menus: 0, navigation: [], destinations: [], errors: [], captcha: 0, validation: 0 }
  const routing = createRouter({ history: createMemoryHistory(), routes: [{ path: '/portal/research/reports/:id', component: {} }] })
  const context = vm.createContext({
    loading: { value: false }, loginAuthenticated: { value: false },
    loginForm: { value: { username: 'admin', password: 'test-password', code: 'test-code' } },
    loginRef: { value: { validate(callback) { calls.validation++; callback(true) } } },
    Cookies: { remove() {}, set() {} },
    route: { query: {} }, redirect: { value: target },
    userStore: {
      async login() { calls.login++; if (loginFailure) throw new Error('captcha invalid') },
      async getInfo() { calls.info++ }
    },
    permissionStore: { async generateRoutes() {
      calls.menus++
      if (menuFailure && calls.menus === 1) throw new Error('menu unavailable')
      return []
    } },
    router: { addRoute() {}, resolve: routing.resolve, async push(target) { calls.navigation.push(target.path); calls.destinations.push(target) } },
    resolvePostLoginPath: (_user, target) => target, isHttp: () => false,
    ElMessage: { error(message) { calls.errors.push(message) } },
    captchaEnabled: { value: true }, getCode() { calls.captcha++ }
  })
  vm.runInContext(actions, context)
  return { context, calls }
}

const settled = () => new Promise(resolve => setImmediate(resolve))

test('post-login menu failure can retry without resubmitting the consumed captcha', async () => {
  const { context, calls } = loginFlow({ menuFailure: true })
  context.handleLogin()
  await settled()
  assert.equal(context.loading.value, false)
  assert.equal(context.loginAuthenticated.value, true)
  assert.equal(calls.login, 1)
  assert.equal(calls.navigation.length, 0)
  assert.match(calls.errors[0], /菜单加载失败/)
  context.handleLogin()
  await settled()
  assert.equal(calls.login, 1)
  assert.equal(calls.validation, 1)
  assert.equal(calls.menus, 2)
  assert.deepEqual(calls.navigation, ['/portal/research/reports/sample'])
})

test('authentication failure refreshes captcha and does not load menus or navigate', async () => {
  const { context, calls } = loginFlow({ loginFailure: true })
  context.handleLogin()
  await settled()
  assert.equal(context.loginAuthenticated.value, false)
  assert.equal(context.loading.value, false)
  assert.equal(context.loginForm.value.password, '')
  assert.equal(calls.captcha, 1)
  assert.equal(calls.info, 0)
  assert.equal(calls.navigation.length, 0)
})

test('login navigation retains deep-link query parameters and hash', async () => {
  const { context, calls } = loginFlow({ target: '/portal/research/reports/sample?tab=versions#chapter-2' })
  context.handleLogin()
  await settled()
  const destination = calls.destinations[0]
  assert.equal(destination.path, '/portal/research/reports/sample')
  assert.equal(destination.query.tab, 'versions')
  assert.equal(destination.hash, '#chapter-2')
})
