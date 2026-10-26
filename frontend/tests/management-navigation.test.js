import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as Vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import {
  buildManagementNavigation,
  findNavigationGroup,
  resolveActiveNavigation,
  resolveNavigationPath
} from '../src/utils/management-navigation.js'

const page = (path, title = path, extra = {}) => ({ path, component: () => {}, meta: { title }, ...extra })
const directory = (path, children, extra = {}) => ({ path, component: 'Layout', children, ...extra })
const leafMenus = menus => menus.flatMap(menu => menu.children ? leafMenus(menu.children) : [menu])

test('available modules follow the eleven-module requirements order regardless of backend root order', () => {
  const menus = buildManagementNavigation([
    directory('/monitor', [page('server'), page('job')]),
    directory('/system', [page('config'), page('user'), page('role')]),
    directory('/pipeline', [page('template'), page('report'), page('knowledge'), page('governance'), page('source'), page('dashboard')])
  ])
  assert.deepEqual(menus.map(menu => menu.meta.title), [
    '管理首页', '用户管理', '采集管理', '资料库管理', '报告管理', '模板管理', '系统配置', '运行日志'
  ])
  assert.equal(menus.find(menu => menu.meta.title === '报告管理').path, '/pipeline/report')
  assert.deepEqual(menus.find(menu => menu.meta.title === '用户管理').children.map(menu => menu.path), ['/system/user', '/system/role'])
})

test('single filter, report and digest entries are direct links with independent active states', () => {
  const sharedReportComponent = () => {}
  const inputs = [directory('/pipeline', [
    page('filter', '过滤结果与评估'),
    page('report', '科研报告', { component: sharedReportComponent }),
    page('digest', '简报管理', { component: sharedReportComponent })
  ])]
  const original = JSON.stringify(inputs)
  const menus = buildManagementNavigation(inputs)
  assert.deepEqual(menus.map(menu => menu.meta.title), ['报告管理', '简报管理'])
  assert.deepEqual(menus.map(menu => menu.path), ['/pipeline/report', '/pipeline/digest'])
  assert.ok(menus.every(menu => !menu.children && !menu.meta.navigationGroup))
  for (const menu of menus) {
    assert.equal(resolveActiveNavigation({ path: menu.path }, menus), menu.path)
    assert.equal(findNavigationGroup({ path: menu.path }, menus)?.path, menu.path)
    assert.equal(resolveActiveNavigation({ path: `${menu.path}/detail`, meta: { activeMenu: menu.path } }, menus), menu.path)
  }
  assert.equal(menus[0].component, menus[1].component)
  assert.equal(JSON.stringify(inputs), original)
})

test('report management keeps its group when multiple authorized entries are available', () => {
  const menus = buildManagementNavigation([directory('/pipeline', [page('report', '科研报告'), page('manuscript', '论文生成')])])
  assert.equal(menus[0].meta.title, '报告管理')
  assert.equal(menus[0].alwaysShow, true)
  assert.deepEqual(menus[0].children.map(menu => menu.path), ['/pipeline/report', '/pipeline/manuscript'])
  assert.equal(resolveActiveNavigation({ path: '/pipeline/manuscript' }, menus), '/pipeline/manuscript')
  assert.equal(findNavigationGroup({ path: '/pipeline/manuscript' }, menus)?.path, '/_management/reports')
})

test('backend default empty and whitespace query strings keep every available module', () => {
  const paths = [
    '/pipeline/dashboard', '/system/user', '/pipeline/source',
    '/pipeline/intelligence', '/pipeline/knowledge', '/pipeline/report', '/pipeline/digest',
    '/pipeline/template', '/pipeline/model', '/monitor/server'
  ]
  const data = paths.map((path, index) => page(path, path, { hidden: false, query: index % 2 ? '  \n  ' : '' }))
  const snapshot = JSON.stringify(data)
  const menus = buildManagementNavigation(data.toReversed())
  assert.deepEqual(menus.map(menu => menu.meta.title), [
    '管理首页', '用户管理', '采集管理', '数据管理', '资料库管理',
    '报告管理', '简报管理', '模板管理', '系统配置', '运行日志'
  ])
  assert.deepEqual(leafMenus(menus).map(menu => menu.path), paths)
  assert.ok(leafMenus(menus).every(menu => menu.query === undefined))
  assert.equal(JSON.stringify(data), snapshot)
})

test('no placeholder modules, missing components, hidden descendants, empty directories or parameterized detail links', () => {
  const menus = buildManagementNavigation([
    directory('/pipeline', [
      page('dashboard'),
      page('intelligence/detail', '详情', { hidden: true }),
      page('filter', '过滤', { component: undefined }),
      page('knowledge', '资料库', { component: undefined }),
      page('digest', '简报', { component: undefined }),
      page('intelligence/:id', '详情'),
      directory('empty', []),
      page('broken-query', '坏查询', { query: '{broken' })
    ]),
    directory('/system', [page('user')], { hidden: true })
  ])
  assert.deepEqual(menus.map(menu => menu.meta.title), ['管理首页'])
  assert.deepEqual(buildManagementNavigation([]), [])
})

test('absolute paths survive nested ParentView grouping, query metadata and source routes are preserved', () => {
  const query = '{"status":"failed","page":1}'
  const data = [directory('/system', [directory('log', [
    page('operlog', '操作日志', { query, name: 'Operlog', permissions: ['monitor:operlog:list'], meta: { title: '操作日志', icon: 'form', noCache: true } }),
    page('/monitor/logininfor', '登录日志')
  ], { component: 'ParentView' })])]
  const original = JSON.stringify(data)
  const menus = buildManagementNavigation(data)
  assert.equal(menus[0].meta.title, '运行日志')
  const links = leafMenus(menus)
  assert.deepEqual(links.map(menu => menu.path), ['/system/log/operlog', '/monitor/logininfor'])
  assert.equal(links[0].query, query)
  assert.equal(links[0].name, 'Operlog')
  assert.deepEqual(links[0].permissions, ['monitor:operlog:list'])
  assert.equal(links[0].meta.noCache, true)
  assert.notEqual(links[0].meta, data[0].children[0].children[0].meta)
  assert.equal(JSON.stringify(data), original)
})

test('duplicate paths and model configuration entries appear once with an active alias for the old model route', () => {
  const menus = buildManagementNavigation([
    directory('/pipeline', [page('model'), page('source'), page('/pipeline/source/')]),
    directory('/ai', [page('model')])
  ])
  assert.deepEqual(leafMenus(menus).map(menu => menu.path), ['/pipeline/source', '/pipeline/model'])
  assert.equal(resolveActiveNavigation({ path: '/ai/model' }, menus), '/pipeline/model')
  const legacyOnly = buildManagementNavigation([directory('/ai', [page('model')])])
  assert.deepEqual(leafMenus(legacyOnly).map(menu => menu.path), ['/ai/model'])
})

test('unmapped authorized pages and external links remain reachable without inventing routes', () => {
  const inputs = [directory('/tool', [page('swagger'), page('custom', '自定义页面')]), page('https://example.com/docs', '外部文档', { component: undefined })]
  assert.deepEqual(leafMenus(buildManagementNavigation(inputs)).map(menu => menu.path), ['/tool/custom', 'https://example.com/docs'])
})

test('system configuration starts with model and prompts, then parameters and dictionaries', () => {
  const inputs = [
    directory('/system', [page('menu'), page('dict'), page('config')]),
    directory('/tool', [page('custom')]),
    directory('/pipeline', [page('model')])
  ]
  const original = JSON.stringify(inputs)
  const menus = buildManagementNavigation(inputs)
  assert.deepEqual(menus.find(menu => menu.meta.title === '系统配置').children.map(menu => menu.path), [
    '/pipeline/model', '/system/config', '/system/dict', '/system/menu', '/tool/custom'
  ])
  assert.equal(JSON.stringify(inputs), original)
  const withoutModel = buildManagementNavigation([directory('/system', [page('menu'), page('config')])])
  assert.deepEqual(leafMenus(withoutModel).map(menu => menu.path), ['/system/config', '/system/menu'])
})

test('only the specified upstream template destinations are omitted, including ruoyi iframe links', () => {
  const inputs = [
    directory('/ai', [page('chat'), page('custom')]),
    directory('/tool', [page('swagger'), page('custom')]),
    directory('/monitor', [page('druid'), page('server'), page('job')]),
    ...['http://ruoyi.vip', 'https://ruoyi.vip/', 'https://ruoyi.vip/docs?from=menu', 'https://RUOYI.VIP'].map(path => page(path)),
    page('/upstream-frame', '模板外链', { meta: { title: '模板外链', link: 'https://ruoyi.vip' } }),
    page('https://example.com/docs'),
    page('https://ruoyi.vip.example.com/docs'),
    page('https://example.com/?next=https://ruoyi.vip'),
    page('/custom-frame', '自定义外链', { meta: { title: '自定义外链', link: 'https://example.com' } })
  ]
  const original = JSON.stringify(inputs)
  assert.deepEqual(leafMenus(buildManagementNavigation(inputs)).map(menu => menu.path), [
    '/ai/custom', '/tool/custom', 'https://example.com/docs', 'https://ruoyi.vip.example.com/docs',
    'https://example.com/?next=https://ruoyi.vip', '/custom-frame', '/monitor/server', '/monitor/job'
  ])
  assert.equal(JSON.stringify(inputs), original)
})

test('destination deduplication ignores query key order while preserving distinct filtered entries', () => {
  const menus = buildManagementNavigation([directory('/pipeline', [
    page('source', '来源甲', { query: '{"status":"failed","filters":{"kind":"news"}}' }),
    page('source', '来源甲重复', { query: '{"filters":{"kind":"news"},"status":"failed"}' }),
    page('source', '来源乙', { query: '{"status":"failed","filters":{"kind":"paper"}}' })
  ])])
  assert.equal(leafMenus(menus).length, 2)
})

test('path resolution does not prepend a virtual group or duplicate an absolute child path', () => {
  assert.equal(resolveNavigationPath('/_management/users', '/system/user'), '/system/user')
  assert.equal(resolveNavigationPath('/system/user', ''), '/system/user')
  assert.equal(resolveNavigationPath('/system', 'user'), '/system/user')
  assert.equal(resolveNavigationPath('/system/', '/monitor/job/'), '/monitor/job')
  assert.equal(resolveNavigationPath('/system', 'https://example.com/docs'), 'https://example.com/docs')
})

test('the actual SidebarItem renders group children as real links and preserves default queries', async () => {
  const source = readFileSync(new URL('../src/layout/components/Sidebar/SidebarItem.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source, { filename: 'SidebarItem.vue' })
  const script = compileScript(descriptor, { id: 'navigation-test', inlineTemplate: true }).content
    .replace(/import \{([^}]+)\} from "vue"/, (_match, bindings) => `const {${bindings.replace(/ as /g, ': ')}} = Vue`)
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.SidebarItem =')
  const AppLink = Vue.defineComponent({
    props: ['to'],
    setup: (props, { slots }) => () => Vue.h('a', { 'data-to': JSON.stringify(props.to) }, slots.default?.())
  })
  const context = vm.createContext({ Vue, ref: Vue.ref, AppLink, resolveNavigationPath })
  vm.runInContext(script, context)
  const menus = buildManagementNavigation([directory('/pipeline', [
    page('source', '数据源'), page('task', '任务', { query: '{"status":"failed"}' })
  ])])
  const app = Vue.createSSRApp({ render: () => Vue.h(context.SidebarItem, { item: menus[0], basePath: menus[0].path }) })
  app.component('svg-icon', { render: () => null })
  app.component('el-menu-item', {
    props: ['index'],
    render() { return Vue.h('li', { 'data-index': this.index }, [this.$slots.default?.(), this.$slots.title?.()]) }
  })
  app.component('el-sub-menu', {
    props: ['index'],
    render() { return Vue.h('ul', { 'data-index': this.index }, [this.$slots.title?.(), this.$slots.default?.()]) }
  })
  const html = await renderToString(app)
  assert.match(html, /采集管理/)
  assert.match(html, /data-index="\/pipeline\/source"/)
  assert.match(html, /data-index="\/pipeline\/task"/)
  assert.match(html, /&quot;path&quot;:&quot;\/pipeline\/task&quot;,&quot;query&quot;:\{&quot;status&quot;:&quot;failed&quot;\}/)
  assert.doesNotMatch(html, /data-to="[^"\n]*_management/)
})

test('active state follows explicit activeMenu and longest visible ancestor, never matching sibling prefixes', () => {
  const menus = buildManagementNavigation([
    directory('/pipeline', [page('intelligence'), page('source')]),
    directory('/system', [page('user'), page('role'), page('dict')]),
    directory('/monitor', [page('job')])
  ])
  for (const [path, activeMenu, expected] of [
    ['/pipeline/intelligence/detail', undefined, '/pipeline/intelligence'],
    ['/system/user-auth/role/1', '/system/user', '/system/user'],
    ['/system/role-auth/user/1', '/system/role', '/system/role'],
    ['/system/dict-data/index/1', '/system/dict', '/system/dict'],
    ['/monitor/job-log/index/1', '/monitor/job', '/monitor/job'],
    ['/pipeline/sources', undefined, '/pipeline/sources'],
    ['/pipeline/intelligence/detail', '/unauthorized/menu', '/unauthorized/menu']
  ]) {
    assert.equal(resolveActiveNavigation({ path, meta: { activeMenu } }, menus), expected)
  }
})
