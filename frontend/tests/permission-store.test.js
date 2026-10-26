import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as Vue from 'vue'
import * as navigation from '../src/utils/management-navigation.js'
import { isManagementIdentity } from '../src/utils/portal/auth.js'

// 执行实际 store action，以 API stub 检查异步失败和重试；不依赖页面源码字符串断言。
function permissionStore(getRouters, { constantRoutes = [], dynamicRoutes = [], views = [], allowedRoles = [], allowedPermissions = [] } = {}) {
  const source = readFileSync(new URL('../src/store/modules/permission.js', import.meta.url), 'utf8')
    .replace(/^import .*\n/gm, '')
    .replace("const modules = import.meta.glob('./../../views/**/*.vue')", 'const modules = viewModules')
    .replace('export function filterDynamicRoutes', 'function filterDynamicRoutes')
    .replace('export const loadView', 'const loadView')
    .replace('export default usePermissionStore', 'globalThis.result = usePermissionStore')
  const addedRoutes = []
  const context = vm.createContext({
    getRouters,
    router: { addRoute: route => addedRoutes.push(route) },
    constantRoutes, dynamicRoutes,
    viewModules: Object.fromEntries(views.map(view => [`../../views/${view}.vue`, async () => ({})])),
    Layout: {}, ParentView: {}, InnerLink: {},
    auth: {
      hasPermiOr: values => values.some(value => allowedPermissions.includes(value)),
      hasRoleOr: values => values.some(value => allowedRoles.includes(value))
    },
    isManagementIdentity, ...navigation,
    defineStore: (_name, options) => Vue.reactive(Object.assign(options.state(), options.actions))
  })
  vm.runInContext(source, context)
  return { store: context.result, addedRoutes }
}

// 执行真实 SFC 的 setup，使用 Vue 的实际 computed/watch/nextTick；仅替换外部依赖与 DOM 尺寸。
function layoutSetup(file, store, settingsStore, route = Vue.reactive({ path: '/pipeline/dashboard', meta: {} })) {
  const source = readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8')
    .match(/<script setup[^>]*>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*\n/gm, '')
  const mounted = []
  const unmounted = []
  const pushed = []
  const opened = []
  const appStore = Vue.reactive({ sidebar: { opened: false, hide: false }, toggleSideBarHide(value) { this.sidebar.hide = value } })
  const context = vm.createContext({
    ...Vue, ...navigation,
    useAppStore: () => appStore, useSettingsStore: () => settingsStore, usePermissionStore: () => store,
    useRoute: () => route, useRouter: () => ({ push: value => pushed.push(value) }),
    getCurrentInstance: () => ({ proxy: {} }), defineExpose: () => {},
    onMounted: callback => mounted.push(callback), onBeforeUnmount: callback => unmounted.push(callback),
    handleThemeStyle: () => {},
    isExternal: path => /^(https?:|mailto:|tel:)/.test(path),
    window: { addEventListener() {}, removeEventListener() {}, open: (...args) => opened.push(args) },
    document: { body: { getBoundingClientRect: () => ({ width: 1280 }) } }
  })
  const scope = Vue.effectScope()
  scope.run(() => vm.runInContext(source, context))
  return {
    appStore, pushed, opened,
    get: expression => vm.runInContext(expression, context),
    mount: () => mounted.forEach(callback => callback()),
    stop: () => { unmounted.forEach(callback => callback()); scope.stop() }
  }
}

function managementFixture() {
  return permissionStore(async () => ({ data: [
    { path: '/system', component: 'Layout', meta: { title: '系统管理' }, children: [{ path: 'role', component: 'system/role/index', meta: { title: '角色管理' } }] },
    { path: '/pipeline', component: 'Layout', meta: { title: '管网情报' }, children: [
      { path: 'dashboard', component: 'pipeline/dashboard/index', meta: { title: '工作台' } },
      { path: 'source', component: 'pipeline/source/index', query: '{"status":"failed"}', meta: { title: '数据源' } },
      { path: 'task', component: 'pipeline/task/index', meta: { title: '任务' } },
      { path: 'model', component: 'pipeline/model/index', meta: { title: '模型' } }
    ] }
  ] }), { views: ['system/role/index', 'pipeline/dashboard/index', 'pipeline/source/index', 'pipeline/task/index', 'pipeline/model/index'] })
}

function projectDynamicRoutes() {
  const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
    .replace(/^import .*\n/gm, '')
    .replace(/^export const /gm, 'const ')
    .replace('export default router;', 'globalThis.result = dynamicRoutes')
  const context = vm.createContext({ Layout: {}, createWebHistory: () => ({}), createRouter: () => ({ beforeEach() {} }), legacyDetailGuard: () => () => {}, ElMessage: { warning() {} } })
  vm.runInContext(source, context)
  return context.result
}

test('real backend query-empty shape survives generation and Settings reload alongside explicit dynamic entries', async t => {
  const backend = [
    { path: '/monitor', component: 'Layout', hidden: false, query: '', meta: { title: '系统监控' }, children: [{ path: 'server', component: 'monitor/server/index', hidden: false, query: '', meta: { title: '服务监控' } }] },
    { path: '/system', component: 'Layout', hidden: false, query: '', meta: { title: '系统管理' }, children: [{ path: 'user', component: 'system/user/index', hidden: false, query: '', meta: { title: '用户管理' } }] },
    { path: '/pipeline', component: 'Layout', hidden: false, query: '', meta: { title: '管网情报' }, children: [
      ...['dashboard', 'source', 'task', 'intelligence', 'governance', 'report', 'template', 'model'].map(path => ({ path, component: `pipeline/${path}/index`, hidden: false, query: '', meta: { title: path } })),
      { path: 'intelligence/detail', component: 'pipeline/intelligence/detail', hidden: true, query: '', meta: { title: '详情' } }
    ] }
  ]
  const { store } = permissionStore(async () => ({ data: backend }), {
    views: ['monitor/server/index', 'system/user/index', ...backend[2].children.map(route => route.component)],
    allowedRoles: ['admin'], allowedPermissions: ['pipeline:review:list'], dynamicRoutes: projectDynamicRoutes()
  })
  await store.generateRoutes({ roles: ['admin'] })
  const registered = JSON.stringify({ routes: store.routes, defaults: store.defaultRoutes })
  const drawer = layoutSetup('layout/components/Settings/index.vue', store, Vue.reactive({ navType: 1 }))
  t.after(drawer.stop)
  await Vue.nextTick()
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), [
    '管理首页', '用户管理', '采集管理', '数据管理', '资料库管理', '报告管理', '简报管理', '模板管理', '系统配置', '运行日志'
  ])
  assert.equal(store.routes[2].children[0].query, '')
  assert.equal(store.routes[2].children.at(-1).hidden, true)
  assert.equal(JSON.stringify({ routes: store.routes, defaults: store.defaultRoutes }), registered)
})

test('the real filter management entry remains absent without review-list permission', async () => {
  const { store, addedRoutes } = permissionStore(async () => ({ data: [] }), {
    allowedRoles: ['admin'], dynamicRoutes: projectDynamicRoutes()
  })
  await store.generateRoutes({ roles: ['admin'] })
  assert.equal(addedRoutes.some(route => route.path === '/pipeline/filter'), false)
  assert.deepEqual(Array.from(store.navigationRoutes, menu => menu.meta.title), ['资料库管理', '简报管理'])
})

test('Settings immediate watcher after a page refresh retains management navigation, not defaultRoutes', async t => {
  const { store } = managementFixture()
  await store.generateRoutes({ roles: ['admin'] })
  const settings = Vue.reactive({ navType: 1 })
  const expected = Array.from(store.sidebarRouters, menu => menu.meta.title)
  const registered = JSON.stringify(store.defaultRoutes)
  const layout = layoutSetup('layout/components/Settings/index.vue', store, settings)
  t.after(layout.stop)
  await Vue.nextTick()
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), expected)
  assert.equal(layout.appStore.sidebar.hide, false)
  assert.equal(layout.appStore.sidebar.opened, true)
  assert.equal(JSON.stringify(store.defaultRoutes), registered)
})

test('Settings mounted before async routes also keeps the new navigation after loading', async t => {
  const { store } = managementFixture()
  const settings = Vue.reactive({ navType: 1 })
  const layout = layoutSetup('layout/components/Settings/index.vue', store, settings)
  t.after(layout.stop)
  assert.equal(store.sidebarRouters.length, 0)
  await store.generateRoutes({ roles: ['admin'] })
  await Vue.nextTick()
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), ['管理首页', '用户管理', '采集管理', '系统配置'])
})

test('switching mixed, top and side layouts restores independent navigation without mutating route data', async t => {
  const { store } = managementFixture()
  await store.generateRoutes({ roles: ['admin'] })
  const settings = Vue.reactive({ navType: 2 })
  const route = Vue.reactive({ path: '/pipeline/source', meta: {} })
  const registered = JSON.stringify({ routes: store.routes, defaults: store.defaultRoutes })
  const prototype = JSON.stringify(store.navigationRoutes)
  const topnav = layoutSetup('components/TopNav/index.vue', store, settings, route)
  const drawer = layoutSetup('layout/components/Settings/index.vue', store, settings, route)
  t.after(topnav.stop)
  t.after(drawer.stop)
  for (let round = 0; round < 3; round++) {
    settings.navType = 2
    await Vue.nextTick()
    assert.equal(topnav.get('activeMenu.value'), '/_management/collection')
    assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.path), ['/pipeline/source', '/pipeline/task'])
    for (const mode of [3, 1]) {
      settings.navType = mode
      await Vue.nextTick()
      assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), ['管理首页', '用户管理', '采集管理', '系统配置'])
      assert.equal(drawer.appStore.sidebar.hide, mode === 3)
    }
  }
  store.sidebarRouters[2].children[0].path = '/accidental-local-edit'
  store.sidebarRouters[2].children[0].meta.title = 'local only'
  store.topbarRouters[0].meta.title = 'topbar local only'
  store.restoreSidebarRouters()
  assert.equal(store.sidebarRouters[2].children[0].path, '/pipeline/source')
  assert.equal(JSON.stringify(store.navigationRoutes), prototype)
  assert.equal(JSON.stringify({ routes: store.routes, defaults: store.defaultRoutes }), registered)
})

test('TopNav repeatedly selects real group children and navigates direct entries without duplicated prefixes', async t => {
  const { store } = managementFixture()
  await store.generateRoutes({ roles: ['admin'] })
  const settings = Vue.reactive({ navType: 2 })
  const route = Vue.reactive({ path: '/pipeline/source', meta: {} })
  const prototype = JSON.stringify(store.navigationRoutes)
  const topnav = layoutSetup('components/TopNav/index.vue', store, settings, route)
  t.after(topnav.stop)
  topnav.mount()
  for (let round = 0; round < 4; round++) {
    topnav.get("handleSelect('/_management/users')")
    assert.equal(store.sidebarRouters[0].path, '/system/role')
    topnav.get("handleSelect('/_management/collection')")
    assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.path), ['/pipeline/source', '/pipeline/task'])
    assert.equal(store.sidebarRouters[0].query, '{"status":"failed"}')
    assert.equal(topnav.get('activeMenu.value'), '/_management/collection')
  }
  topnav.get("handleSelect('/pipeline/dashboard')")
  assert.equal(topnav.pushed[0].path, '/pipeline/dashboard')
  assert.equal(topnav.appStore.sidebar.hide, true)
  topnav.get("handleSelect('/not-an-authorized-menu')")
  assert.equal(topnav.pushed.length, 1)
  route.path = '/pipeline/model'
  await Vue.nextTick()
  assert.equal(topnav.get('activeMenu.value'), '/_management/settings')
  assert.equal(store.sidebarRouters[0].path, '/pipeline/model')
  assert.equal(JSON.stringify(store.navigationRoutes), prototype)
})

test('both horizontal menus keep every remaining menu in More and TopBar ignores a mixed sidebar subset', async t => {
  const { store } = managementFixture()
  await store.generateRoutes({ roles: ['admin'] })
  const settings = Vue.reactive({ navType: 3 })
  store.selectNavigationGroup('/_management/collection')
  const expected = Array.from(store.navigationRoutes, menu => menu.path)
  const snapshot = JSON.stringify(store.navigationRoutes)
  for (const file of ['components/TopNav/index.vue', 'layout/components/TopBar/index.vue']) {
    const layout = layoutSetup(file, store, settings)
    t.after(layout.stop)
    for (const count of [0, 1, 3, 4, 20]) {
      layout.get(`visibleNumber.value = ${count}`)
      const visible = Array.from(layout.get('topMenus.value'), menu => menu.path)
      const more = Array.from(layout.get('moreRoutes.value'), menu => menu.path)
      assert.deepEqual(visible.concat(more), expected)
      assert.deepEqual(more, expected.slice(count))
    }
  }
  assert.equal(JSON.stringify(store.navigationRoutes), snapshot)
})

test('only authorized dynamic management entries join navigation; other routes are registered without promotion', async () => {
  const entry = (path, title, extra = {}) => ({
    path, roles: ['admin'], meta: { managementEntry: true },
    children: [{ path: '', component: () => {}, meta: { title } }], ...extra
  })
  const { store, addedRoutes } = permissionStore(async () => ({ data: [] }), {
    allowedRoles: ['admin'],
    dynamicRoutes: [
      entry('/pipeline/knowledge', '资料库'),
      entry('/pipeline/digest', '周期简报'),
      entry('/pipeline/report', '科研成果'),
      entry('/plain-dynamic', '普通动态页面', { meta: {} }),
      entry('/hidden-detail', '隐藏详情', { hidden: true }),
      entry('/role-denied', '无此角色', { roles: ['other'] }),
      entry('/permission-denied', '无此权限', { permissions: ['secret:list'] }),
      entry('/missing-page', '组件不可用', { children: [{ path: '', meta: { title: '不可用' } }] })
    ],
    constantRoutes: [entry('/static-only', '隐藏静态', { hidden: true })]
  })
  const registered = await store.generateRoutes({ roles: ['admin'] })
  assert.equal(registered.length, 0)
  assert.deepEqual(Array.from(store.navigationRoutes, menu => menu.meta.title), ['资料库管理', '报告管理', '简报管理'])
  assert.equal(store.navigationRoutes[1].path, '/pipeline/report')
  assert.equal(store.navigationRoutes[1].meta.title, '报告管理')
  assert.equal(store.navigationRoutes[1].children, undefined)
  assert.equal(store.navigationRoutes[2].path, '/pipeline/digest')
  assert.equal(store.navigationRoutes[2].children, undefined)
  assert.deepEqual(addedRoutes.map(route => route.path), [
    '/pipeline/knowledge', '/pipeline/digest', '/pipeline/report', '/plain-dynamic', '/hidden-detail', '/missing-page'
  ])
  assert.equal(store.defaultRoutes.length, 1)
  assert.equal(store.defaultRoutes[0].path, '/static-only')
})

test('a managementEntry flag cannot bypass the existing dynamic role check', async () => {
  const { store, addedRoutes } = permissionStore(async () => ({ data: [] }), {
    dynamicRoutes: [{ path: '/pipeline/knowledge', roles: ['admin'], meta: { managementEntry: true }, children: [{ path: '', component: () => {}, meta: { title: '资料库' } }] }]
  })
  await store.generateRoutes({ permissions: ['*:*:*'] })
  assert.equal(addedRoutes.length, 0)
  assert.equal(store.navigationRoutes.length, 0)
  assert.equal(store.sidebarRouters.length, 0)
})

test('menu API failure rejects route loading and a subsequent retry succeeds', async () => {
  const failure = new Error('menu API unavailable')
  let attempts = 0
  const { store } = permissionStore(async () => {
    if (++attempts === 1) throw failure
    return { data: [{ path: '/pipeline', component: 'Layout' }] }
  })
  await assert.rejects(store.generateRoutes({ roles: ['admin'] }), failure)
  assert.equal(store.routes.length, 0)
  const routes = await store.generateRoutes({ roles: ['admin'] })
  assert.equal(routes.length, 1)
  assert.equal(routes[0].path, '/pipeline')
  assert.equal(store.sidebarRouters.length, 0) // 空目录不生成可点击入口。
})

test('malformed menu response rejects route loading instead of leaving login pending', async () => {
  const { store } = permissionStore(async () => ({ data: null }))
  await assert.rejects(store.generateRoutes())
})

test('management navigation uses backend menus while registration keeps hidden and unavailable routes', async () => {
  const data = [{ path: '/pipeline', component: 'Layout', children: [
    { path: 'task', component: 'pipeline/task/index', meta: { title: '采集任务' } },
    { path: 'dashboard', component: 'pipeline/dashboard/index', meta: { title: '工作台' } },
    { path: 'governance', component: 'pipeline/governance/index', meta: { title: '数据治理' } },
    { path: 'intelligence/detail', component: 'pipeline/intelligence/detail', hidden: true, meta: { title: '详情' } },
    { path: 'knowledge', component: 'missing/view', meta: { title: '资料库' } }
  ] }]
  const original = JSON.stringify(data)
  const { store, addedRoutes } = permissionStore(async () => ({ data }), {
    views: ['pipeline/task/index', 'pipeline/dashboard/index', 'pipeline/governance/index', 'pipeline/intelligence/detail'],
    constantRoutes: [{ path: '/pipeline/template', hidden: true, component: () => {}, meta: { title: '模板' } }],
    dynamicRoutes: [{ path: '/privileged', permissions: ['system:user:edit'] }]
  })
  const registered = await store.generateRoutes({ roles: ['admin'] })
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), ['管理首页', '采集管理'])
  assert.equal(registered[0].children.length, 4)
  assert.equal(registered[0].children[2].hidden, true)
  assert.equal(store.defaultRoutes[1].children.length, 4)
  assert.equal(store.topbarRouters[0].path, '/pipeline/dashboard')
  assert.equal(JSON.stringify(data), original)
  assert.equal(addedRoutes.length, 0)
})

test('ordinary users keep their existing menu filter and wildcard managers use the management projection', async () => {
  const data = [
    { path: '/system', component: 'Layout', children: [{ path: 'user', component: 'system/user/index', meta: { title: '用户管理' } }] },
    { path: '/pipeline', component: 'Layout', meta: { title: '管网情报' }, children: [{ path: 'task', component: 'pipeline/task/index', meta: { title: '采集任务' } }] }
  ]
  const { store } = permissionStore(async () => ({ data }), { views: ['system/user/index', 'pipeline/task/index'] })
  await store.generateRoutes({ roles: ['common'] })
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.path), ['/pipeline'])
  assert.equal(store.routes.length, 2)
  await store.generateRoutes({ permissions: ['*:*:*'] })
  assert.deepEqual(Array.from(store.sidebarRouters, menu => menu.meta.title), ['用户管理', '采集管理'])
  assert.equal(store.routes.length, 2)
})

test('personal chat is not registered while shared system monitor and model routes remain', async () => {
  const menu = (path, component, permissions) => ({ path, component, permissions, query: '', meta: { title: path } })
  const data = [
    { path: '/system', component: 'Layout', children: [menu('menu', 'system/menu/index', ['system:menu:list']), menu('dict', 'system/dict/index'), menu('config', 'system/config/index')] },
    { path: '/ai', component: 'Layout', children: [menu('chat', 'ai/chat/index', ['ai:chat:list'])] },
    { path: '/tool', component: 'Layout', children: [menu('swagger', 'tool/swagger/index')] },
    { path: '/monitor', component: 'Layout', children: [menu('druid', 'monitor/druid/index'), menu('server', 'monitor/server/index')] },
    { path: '/pipeline', component: 'Layout', children: [menu('model', 'pipeline/model/index', ['ai:model:list'])] },
    menu('https://ruoyi.vip', undefined), menu('https://example.com/docs', undefined)
  ]
  const { store } = permissionStore(async () => ({ data }), {
    views: ['system/menu/index', 'system/dict/index', 'system/config/index', 'ai/chat/index', 'tool/swagger/index', 'monitor/druid/index', 'monitor/server/index', 'pipeline/model/index']
  })
  const registered = await store.generateRoutes({ roles: ['admin'] })
  assert.deepEqual(Array.from(registered, route => route.path), data.filter(route => route.path !== '/ai').map(route => route.path))
  assert.equal(registered[1].children[0].path, 'swagger')
  assert.equal(registered[2].children[0].path, 'druid')
  assert.ok(!JSON.stringify(registered).includes('ai:chat:list'))
  assert.ok(!JSON.stringify(store.defaultRoutes).includes('ai/chat/index'))
  const settings = store.navigationRoutes.find(menu => menu.meta.title === '系统配置')
  assert.deepEqual(Array.from(settings.children, menu => menu.path), [
    '/pipeline/model', '/system/config', '/system/dict', '/system/menu', 'https://example.com/docs'
  ])
  assert.deepEqual(Array.from(store.navigationRoutes.find(menu => menu.meta.title === '运行日志').children, menu => menu.path), ['/monitor/server'])
})
