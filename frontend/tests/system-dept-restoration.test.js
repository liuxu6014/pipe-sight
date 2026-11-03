import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import AsyncValidator from 'async-validator'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { handleTree, parseStrEmpty } from '../src/utils/ruoyi.js'
import { buildManagementNavigation, findNavigationGroup } from '../src/utils/management-navigation.js'

const read = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const tick = () => new Promise(resolve => setImmediate(resolve))
const Schema = AsyncValidator.default || AsyncValidator
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

// Compile and execute the real setup functions with injected APIs; no backend writes.
function setup(name, dependencies = {}, proxyOverrides = {}) {
  const { descriptor } = parse(read(`views/system/${name}/index.vue`))
  const script = compileScript(descriptor, { id: `dept-${name}` })
  assert.deepEqual(compileTemplate({
    source: descriptor.template.content, id: `dept-${name}`,
    compilerOptions: { bindingMetadata: script.bindings }
  }).errors, [])
  const mounted = [], scope = Vue.effectScope()
  const proxy = {
    useDict: () => ({}), resetForm() {}, handleTree,
    addDateRange: query => query,
    getConfigKey: async () => ({ msg: 'test-password' }),
    $modal: { msgSuccess() {}, confirm: async () => {} },
    $refs: { userRef: { validate: fn => fn(true) }, deptRef: { validate: async () => true } },
    ...proxyOverrides
  }
  const env = {
    ref: Vue.ref, reactive: Vue.reactive, toRefs: Vue.toRefs, watch: Vue.watch, nextTick: Vue.nextTick,
    getCurrentInstance: () => ({ proxy }), onMounted: fn => mounted.push(fn),
    useRouter: () => ({}), useAppStore: () => ({ device: 'desktop' }), getToken: () => 'test',
    listUser: async () => ({ rows: [], total: 0 }),
    deptTreeSelect: async () => ({ data: [] }),
    ...dependencies
  }
  const code = script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"];?\s*$/gm, '')
    .replace(/^import\s*['"][^'"]+['"];?\s*$/gm, '')
    .replaceAll('import.meta.env.VITE_APP_BASE_API', '"/test-api"')
    .replace('export default', 'return')
  const component = new Function(...Object.keys(env), code)(...Object.values(env))
  const state = scope.run(() => component.setup({}, { expose() {} }))
  return { state, mounted, close: () => scope.stop(), template: descriptor.template.content }
}

test('department APIs retain native paths, methods, query and payload objects', async () => {
  const calls = []
  const request = async options => { calls.push(options); return { data: [] } }
  const load = (path, names) => new Function('request', 'parseStrEmpty',
    read(path).replace(/^import .*\n/gm, '').replace(/export function/g, 'function') + `\nreturn { ${names} }`
  )(request, parseStrEmpty)
  const dept = load('api/system/dept.js', 'listDept, listDeptExcludeChild, getDept, addDept, updateDept, delDept')
  const user = load('api/system/user.js', 'deptTreeSelect, listUser, addUser, updateUser, uploadAvatar')
  const query = { deptName: '科研', status: '0' }, payload = { deptId: 101, parentId: 100, deptName: '科研' }
  await dept.listDept(query)
  await dept.listDeptExcludeChild(101)
  await dept.getDept(101)
  await dept.addDept(payload)
  await dept.updateDept(payload)
  await dept.delDept(101)
  await user.deptTreeSelect()
  assert.deepEqual(calls, [
    { url: '/system/dept/list', method: 'get', params: query },
    { url: '/system/dept/list/exclude/101', method: 'get' },
    { url: '/system/dept/101', method: 'get' },
    { url: '/system/dept', method: 'post', data: payload },
    { url: '/system/dept', method: 'put', data: payload },
    { url: '/system/dept/101', method: 'delete' },
    { url: '/system/user/deptTree', method: 'get' }
  ])
  await user.listUser({ deptId: 101 })
  assert.equal(calls.at(-1).params.deptId, 101)
  await user.addUser({ deptId: 101 })
  assert.equal(calls.at(-1).data.deptId, 101)
  await user.updateUser({ userId: 2, deptId: 102 })
  assert.equal(calls.at(-1).data.deptId, 102)
  await user.uploadAvatar({})
  assert.equal(calls.at(-1).headers['Content-Type'], 'multipart/form-data')
})

test('user department tree loads, filters users from page one and resets selection', async t => {
  const queries = [], filters = [], selections = []
  const tree = [{ id: 100, label: '总部', children: [{ id: 101, label: '科研部' }] }]
  const h = setup('user', {
    deptTreeSelect: async () => ({ data: tree }),
    listUser: async query => {
      queries.push({ ...query })
      return { rows: [{ userId: 2, dept: { deptId: 101, deptName: '科研部' } }], total: 1 }
    }
  }, { $refs: { deptTreeRef: { filter: value => filters.push(value), setCurrentKey: value => selections.push(value) } } })
  t.after(h.close)
  h.mounted.forEach(fn => fn())
  await tick()
  const s = h.state
  assert.deepEqual(s.deptOptions.value, tree)
  assert.equal(s.userList.value[0].dept.deptName, '科研部')
  s.deptName.value = '科研'
  await Vue.nextTick()
  assert.deepEqual(filters, ['科研'])
  assert.equal(s.filterNode('科研', tree[0].children[0]), true)
  assert.equal(s.filterNode('销售', tree[0].children[0]), false)
  assert.equal(s.filterNode('', tree[0]), true)
  s.queryParams.value.pageNum = 5
  s.handleNodeClick(tree[0].children[0])
  await tick()
  assert.equal(queries.at(-1).deptId, 101)
  assert.equal(queries.at(-1).pageNum, 1)
  s.resetQuery()
  await tick()
  assert.equal(queries.at(-1).deptId, undefined)
  assert.equal(s.deptName.value, '')
  assert.deepEqual(selections, [null])
  assert.equal(s.columns.value.deptName.visible, true)
  assert.match(h.template, /prop="dept\.deptName"/)
  assert.match(h.template, /v-model="form\.deptId"/)
  assert.match(h.template, /@node-click="handleNodeClick"/)
})

test('user create and edit submit the selected department and preserve role assignments', async t => {
  const writes = []
  const h = setup('user', {
    getUser: async id => ({ data: { userId: id, deptId: 101, nickName: '测试用户' }, roles: [{ roleId: 3 }], roleIds: [3] }),
    addUser: async data => writes.push({ type: 'add', ...data }),
    updateUser: async data => writes.push({ type: 'update', ...data })
  })
  t.after(h.close)
  const s = h.state
  s.handleAdd()
  await tick()
  assert.equal(s.form.value.deptId, undefined)
  s.form.value.deptId = 102
  s.submitForm()
  await tick()
  assert.equal(writes[0].type, 'add')
  assert.equal(writes[0].deptId, 102)
  s.handleUpdate({ userId: 2 })
  await tick()
  assert.equal(s.form.value.deptId, 101)
  assert.deepEqual(s.form.value.roleIds, [3])
  s.form.value.deptId = 103
  s.submitForm()
  await tick()
  assert.equal(writes[1].type, 'update')
  assert.equal(writes[1].deptId, 103)
  assert.deepEqual(writes[1].roleIds, [3])
  assert.equal(s.open.value, false)
  s.handleUpdate({ userId: 2 })
  await tick()
  s.form.value.deptId = null
  s.submitForm()
  await tick()
  assert.equal(JSON.parse(JSON.stringify(writes[2])).deptId, null)
  assert.deepEqual(writes[2].roleIds, [3])
  assert.match(h.template, /:value-on-clear="null"/)
})

test('native department page builds tree and supports create, excluded-parent edit, delete and expand', async t => {
  const writes = [], excluded = [], queries = []
  const rows = [{ deptId: 100, parentId: 0, deptName: '总部' }, { deptId: 101, parentId: 100, deptName: '科研部' }]
  const h = setup('dept', {
    listDept: async query => { queries.push({ ...query }); return { data: structuredClone(rows) } },
    listDeptExcludeChild: async id => { excluded.push(id); return { data: [structuredClone(rows[0])] } },
    getDept: async () => ({ data: { ...rows[1], status: '0' } }),
    addDept: async data => writes.push({ type: 'add', ...data }),
    updateDept: async data => writes.push({ type: 'update', ...data }),
    delDept: async id => writes.push({ type: 'delete', deptId: id })
  })
  t.after(h.close)
  await tick()
  const s = h.state
  assert.equal(s.deptList.value[0].children[0].deptId, 101)
  assert.equal(s.loading.value, false)
  s.queryParams.value.deptName = '科研'
  s.queryParams.value.status = '0'
  s.handleQuery()
  await tick()
  assert.deepEqual(queries.at(-1), { deptName: '科研', status: '0' })
  s.handleAdd(rows[0])
  await tick()
  assert.equal(s.form.value.parentId, 100)
  s.form.value.deptName = '新部门'
  s.submitForm()
  await tick()
  assert.equal(writes[0].type, 'add')
  assert.equal(writes[0].parentId, 100)
  s.handleUpdate(rows[1])
  await tick()
  assert.deepEqual(excluded, [101])
  assert.equal(s.deptOptions.value[0].deptId, 0)
  assert.deepEqual(s.deptOptions.value[0].children.map(row => row.deptId), [100])
  s.form.value.deptName = '研发部'
  s.form.value.parentId = 0
  s.submitForm()
  await tick()
  assert.equal(writes[1].type, 'update')
  assert.equal(writes[1].deptId, 101)
  assert.equal(writes[1].deptName, '研发部')
  assert.equal(writes[1].parentId, 0)
  s.handleDelete(rows[1])
  await tick()
  assert.deepEqual(writes[2], { type: 'delete', deptId: 101 })
  s.toggleExpandAll()
  assert.equal(s.refreshTable.value, false)
  await Vue.nextTick()
  assert.equal(s.refreshTable.value, true)
  assert.equal(s.isExpandAll.value, false)
  for (const action of ['add', 'edit', 'remove']) assert.ok(h.template.includes(`system:dept:${action}`))
})

test('empty department list permits first root creation without creating records automatically', async t => {
  const writes = [], rows = []
  const h = setup('dept', {
    listDept: async () => ({ data: structuredClone(rows) }),
    addDept: async data => {
      writes.push({ ...data })
      rows.push({ ...data, deptId: 100 })
    }
  })
  t.after(h.close)
  const s = h.state
  await tick()
  assert.deepEqual(s.deptList.value, [])
  assert.equal(writes.length, 0)
  // Toolbar click passes a MouseEvent, which has no department ID.
  s.handleAdd({ type: 'click' })
  await tick()
  assert.equal(s.form.value.parentId, 0)
  assert.deepEqual(s.deptOptions.value, [{ deptId: 0, deptName: '顶级部门', children: [] }])
  assert.equal(writes.length, 0)
  s.form.value.deptName = '首个部门'
  // Element Plus removes the event trigger before passing rules to async-validator.
  const validationRules = Object.fromEntries(Object.entries(s.rules.value).map(([field, rules]) => [
    field, rules.map(({ trigger, ...rule }) => rule)
  ]))
  await new Schema(validationRules).validate(s.form.value)
  await s.submitForm()
  assert.equal(writes.length, 1)
  assert.equal(writes[0].parentId, 0)
  assert.equal(writes[0].deptName, '首个部门')
  assert.equal(s.deptList.value[0].deptId, 100)
  assert.equal(s.deptList.value[0].deptName, '首个部门')
  s.handleAdd()
  await tick()
  assert.equal(s.form.value.parentId, 0)
  assert.equal(s.deptOptions.value[0].children[0].deptId, 100)
  s.handleAdd({ deptId: 100 })
  await tick()
  assert.equal(s.form.value.parentId, 100)
  // Choosing top level must leave the tree selector available for switching back.
  assert.doesNotMatch(h.template, /v-if="form\.parentId\s*!==?\s*0"/)
  assert.match(h.template, /v-model="form\.parentId"/)
})

test('department list clears loading after failure and supports retry without clearing existing data', async t => {
  let fail = true
  const h = setup('dept', {
    listDept: async () => {
      if (fail) throw new Error('offline')
      return { data: [{ deptId: 100, parentId: 0, deptName: '部门' }] }
    }
  })
  t.after(h.close)
  const s = h.state
  await tick()
  assert.equal(s.loading.value, false)
  assert.deepEqual(s.deptList.value, [])
  fail = false
  const pending = s.getList()
  assert.equal(s.loading.value, true)
  await pending
  assert.equal(s.loading.value, false)
  assert.equal(s.deptList.value[0].deptId, 100)
  fail = true
  await s.getList()
  assert.equal(s.loading.value, false)
  assert.equal(s.deptList.value[0].deptId, 100)
})

for (const isEdit of [false, true]) {
  test(`department ${isEdit ? 'edit' : 'create'} locks validation and request, then unlocks after failure for retry`, async t => {
    const validation = deferred(), request = deferred(), writes = []
    let validations = 0
    const save = data => {
      writes.push({ ...data })
      return writes.length === 1 ? request.promise : Promise.resolve({})
    }
    const h = setup('dept', {
      listDept: async () => ({ data: [] }), addDept: save, updateDept: save
    }, { $refs: { deptRef: { validate: () => ++validations === 1 ? validation.promise : Promise.resolve(true) } } })
    t.after(h.close)
    const s = h.state
    s.handleAdd()
    s.form.value.deptName = '待保存部门'
    if (isEdit) s.form.value.deptId = 101
    const first = s.submitForm()
    assert.equal(s.submitLoading.value, true)
    await s.submitForm()
    assert.equal(validations, 1)
    assert.equal(writes.length, 0)
    validation.resolve(true)
    await tick()
    assert.equal(writes.length, 1)
    assert.equal(writes[0].deptId, isEdit ? 101 : undefined)
    await s.submitForm()
    assert.equal(writes.length, 1)
    s.cancel()
    assert.equal(s.open.value, true)
    request.reject(new Error('save failed'))
    await first
    assert.equal(s.submitLoading.value, false)
    assert.equal(s.open.value, true)
    assert.equal(s.form.value.deptName, '待保存部门')
    await s.submitForm()
    assert.equal(writes.length, 2)
    assert.equal(s.submitLoading.value, false)
    assert.equal(s.open.value, false)
    assert.match(h.template, /:loading="submitLoading"/)
    assert.match(h.template, /:disabled="submitLoading"/)
    assert.match(h.template, /:close-on-click-modal="!submitLoading"/)
    assert.match(h.template, /:close-on-press-escape="!submitLoading"/)
    assert.match(h.template, /:show-close="!submitLoading"/)
  })
}

test('department validation failure releases submit lock and sends no request', async t => {
  let writes = 0, valid = false
  const h = setup('dept', {
    listDept: async () => ({ data: [] }), addDept: async () => { writes++ }
  }, { $refs: { deptRef: { validate: async () => {
    if (!valid) throw { deptName: [{ message: '部门名称不能为空' }] }
    return true
  } } } })
  t.after(h.close)
  const s = h.state
  s.handleAdd()
  await s.submitForm()
  assert.equal(writes, 0)
  assert.equal(s.submitLoading.value, false)
  assert.equal(s.open.value, true)
  valid = true
  s.form.value.deptName = '修正后的部门'
  await s.submitForm()
  assert.equal(writes, 1)
  assert.equal(s.submitLoading.value, false)
})

test('department navigation belongs to users only when authorized and visible', () => {
  const dept = { path: 'dept', component: 'system/dept/index', meta: { title: '部门管理' }, permissions: ['system:dept:list'] }
  const routes = [{ path: '/system', component: 'Layout', children: [dept] }]
  const before = JSON.stringify(routes)
  const menus = buildManagementNavigation(routes)
  assert.equal(menus[0].path, '/_management/users')
  assert.equal(menus[0].children[0].path, '/system/dept')
  assert.equal(menus[0].children[0].meta.title, '部门管理')
  assert.deepEqual(menus[0].children[0].permissions, ['system:dept:list'])
  assert.equal(findNavigationGroup({ path: '/system/dept' }, menus).path, '/_management/users')
  assert.equal(JSON.stringify(routes), before)
  assert.deepEqual(buildManagementNavigation([]), [])
  dept.hidden = true
  assert.deepEqual(buildManagementNavigation(routes), [])
})
