import test from 'node:test'
import assert from 'node:assert/strict'
import { profileFields, validateProfile, validatePasswordChange } from '../src/utils/portal/profile.js'
import fs from 'node:fs'
import * as vue from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

async function mountProfile(api = {}) {
  const source = fs.readFileSync(new URL('../src/views/portal/pages/ProfileView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'profile-test' })
  assert.deepEqual(compileTemplate({ id: 'profile-test', source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  const store = vue.reactive({ id: 7, name: 'account', nickName: 'Before' }), messages = []
  const values = { ...vue, User: {}, Lock: {}, Phone: {}, Message: {}, ArrowRight: {}, InfoFilled: {}, PortalAvatarEditor: {}, useUserStore: () => store, PortalEmptyState: {}, ElMessage: { success: text => messages.push(text) }, profileFields, validateProfile, validatePasswordChange,
    getUserProfile: async () => ({ data: { userName: 'account', nickName: 'Before' } }), updateUserProfile: async () => {}, updateUserPwd: async () => {}, ...api }
  const entries = Object.entries(values).filter(([key]) => /^[A-Za-z_$][\w$]*$/.test(key) && key !== 'default')
  const code = script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '').replace('export default', 'return')
  const component = new Function(...entries.map(([key]) => key), code)(...entries.map(([, value]) => value))
  let page
  const setup = component.setup
  component.setup = (props, context) => { page = setup(props, context); return page }
  component.render = () => null
  const renderer = vue.createRenderer({ createComment: () => ({}), createText: () => ({}), createElement: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
  const app = renderer.createApp(component)
  app.mount({})
  await vue.nextTick(); await new Promise(resolve => setImmediate(resolve))
  return { page, store, messages, close: () => app.unmount() }
}

test('profile updates whitelist self-service fields and exclude identity, roles and passwords', () => {
  assert.deepEqual(profileFields({ nickName: ' 年糕 ', email: ' a@example.com ', phonenumber: '13800138000', sex: '2', userId: 1, roles: ['admin'], password: 'secret' }), { nickName: '年糕', email: 'a@example.com', phonenumber: '13800138000', sex: '2' })
  assert.equal(validateProfile({ nickName: '年糕', email: '', phonenumber: '' }), '')
  assert.ok(validateProfile({ nickName: '', email: '' }))
  assert.ok(validateProfile({ nickName: '年糕', email: 'invalid' }))
  assert.ok(validateProfile({ nickName: '年糕', phonenumber: '123' }))
})

test('password changes reject missing, mismatched, reused and unsupported passwords', () => {
  assert.equal(validatePasswordChange({ oldPassword: 'old-pass', newPassword: 'new-pass', confirmPassword: 'new-pass' }), '')
  for (const fields of [{}, { oldPassword: 'old-pass', newPassword: 'short', confirmPassword: 'short' }, { oldPassword: 'old-pass', newPassword: 'new-pass', confirmPassword: 'different' }, { oldPassword: 'old-pass', newPassword: 'old-pass', confirmPassword: 'old-pass' }, { oldPassword: 'old-pass', newPassword: 'bad<pass', confirmPassword: 'bad<pass' }]) assert.ok(validatePasswordChange(fields))
})

test('profile form only updates the nickname after a successful whitelisted save', async () => {
  const calls = []
  let fail = true
  const ctx = await mountProfile({ updateUserProfile: async value => { calls.push(value); if (fail) throw { msg: '保存失败' } } })
  try {
    assert.equal(ctx.page.isDirty.value, false)
    ctx.page.form.nickName = 'After'
    assert.equal(ctx.page.isDirty.value, true)
    ctx.page.form.userId = 999
    await ctx.page.saveProfile()
    assert.equal(ctx.store.nickName, 'Before')
    assert.equal(ctx.page.saveError.value, '保存失败')
    assert.equal(calls[0].userId, undefined)
    fail = false
    await ctx.page.saveProfile()
    assert.equal(ctx.store.nickName, 'After')
    assert.equal(ctx.page.isDirty.value, false)
    assert.equal(ctx.page.saving.value, false)
  } finally { ctx.close() }
})

test('password fields clear after success and on unmount, with no request for mismatched confirmation', async () => {
  const calls = []
  const ctx = await mountProfile({ updateUserPwd: async (...args) => calls.push(args) })
  Object.assign(ctx.page.password, { oldPassword: 'old-pass', newPassword: 'new-pass', confirmPassword: 'mismatch' })
  await ctx.page.savePassword()
  assert.equal(calls.length, 0)
  ctx.page.password.confirmPassword = 'new-pass'
  await ctx.page.savePassword()
  assert.deepEqual(calls, [['old-pass', 'new-pass']])
  assert.equal(ctx.page.password.oldPassword, '')
  ctx.page.password.oldPassword = 'unsaved-pass'
  ctx.close()
  assert.equal(ctx.page.password.oldPassword, '')
})

test('profile load failure prevents submitting an empty form', async () => {
  let saves = 0
  const ctx = await mountProfile({ getUserProfile: async () => { throw { msg: '加载失败' } }, updateUserProfile: async () => { saves += 1 } })
  try {
    ctx.page.form.nickName = 'After'
    await ctx.page.saveProfile()
    assert.equal(ctx.page.loadError.value, '加载失败')
    assert.equal(saves, 0)
  } finally { ctx.close() }
})
