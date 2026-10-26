import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as vue from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { avatarUrl, validateAvatarFile } from '../src/utils/portal/avatar.js'

test('avatar validates format and size and safely resolves uploaded paths', () => {
  assert.equal(validateAvatarFile({ type: 'image/png', size: 1024 }), '')
  assert.ok(validateAvatarFile({ type: 'image/svg+xml', size: 100 }))
  assert.ok(validateAvatarFile({ type: 'image/jpeg', size: 6 * 1024 * 1024 }))
  assert.ok(validateAvatarFile({ type: 'image/png', size: 0 }))
  assert.equal(avatarUrl('/profile/avatar/a.png', '/dev-api'), '/dev-api/profile/avatar/a.png')
  assert.equal(avatarUrl('/dev-api/profile/avatar/a.png', '/dev-api'), '/dev-api/profile/avatar/a.png')
  assert.equal(avatarUrl('https://example.com/a.png', '/dev-api'), 'https://example.com/a.png')
  assert.equal(avatarUrl('javascript:alert(1)', '/dev-api'), '')
  assert.equal(avatarUrl('', '/dev-api'), '')
})

async function mountEditor(uploadAvatar) {
  const source = fs.readFileSync(new URL('../src/views/portal/components/PortalAvatarEditor.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'avatar-test' })
  assert.deepEqual(compileTemplate({ id: 'avatar-test', source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  const store = vue.reactive({ id: 7, avatar: '/old.png' })
  const values = { ...vue, useUserStore: () => store, uploadAvatar, avatarUrl, validateAvatarFile, PortalUserAvatar: {}, VueCropper: {}, ElMessage: { success() {} } }
  const entries = Object.entries(values).filter(([key]) => /^[A-Za-z_$][\w$]*$/.test(key) && key !== 'default')
  const code = script.content.replace(/^import[^\n]*\n/gm, '').replace('export default', 'return').replaceAll('import.meta.env.VITE_APP_BASE_API', JSON.stringify('/dev-api'))
  const component = new Function(...entries.map(([key]) => key), code)(...entries.map(([, value]) => value))
  let page
  const setup = component.setup
  component.setup = (props, context) => { page = setup(props, context); return page }
  component.render = () => null
  const renderer = vue.createRenderer({ createComment: () => ({}), createText: () => ({}), createElement: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
  const app = renderer.createApp(component); app.mount({})
  page.open.value = true
  page.source.value = 'data:image/png;base64,test'
  page.ready.value = true
  page.cropper.value = { getCropBlob: callback => callback(new Blob(['png'], { type: 'image/png' })) }
  return { page, store, close: () => app.unmount() }
}

test('avatar saves a cropped multipart file and syncs store only after success', async () => {
  let resolve, sent
  const ctx = await mountEditor(data => { sent = data; return new Promise(done => { resolve = done }) })
  try {
    const pending = ctx.page.saveAvatar()
    await vue.nextTick()
    assert.equal(ctx.store.avatar, '/old.png')
    assert.equal(sent.get('avatarfile').name, 'avatar.png')
    resolve({ imgUrl: '/profile/avatar/new.png' })
    await pending
    assert.equal(ctx.store.avatar, '/dev-api/profile/avatar/new.png')
    assert.equal(ctx.page.open.value, false)
  } finally { ctx.close() }
})

test('avatar upload failure and account switching preserve existing avatar', async () => {
  const ctx = await mountEditor(async () => { throw new Error('上传失败') })
  try {
    await ctx.page.saveAvatar()
    assert.equal(ctx.store.avatar, '/old.png')
    assert.equal(ctx.page.error.value, '上传失败')
    assert.equal(ctx.page.saving.value, false)
    assert.equal(ctx.page.open.value, true)
  } finally { ctx.close() }
  let resolve
  const other = await mountEditor(() => new Promise(done => { resolve = done }))
  const pending = other.page.saveAvatar()
  await vue.nextTick()
  other.store.id = 8
  resolve({ imgUrl: '/profile/avatar/wrong-user.png' })
  await pending
  assert.equal(other.store.avatar, '/old.png')
  other.close()
})

test('header and profile share a reactive avatar display with initial fallback', async () => {
  const header = fs.readFileSync(new URL('../src/views/portal/components/PortalHeader.vue', import.meta.url), 'utf8')
  assert.match(header, /<PortalUserAvatar\s*\/>/)
  const { descriptor } = parse(fs.readFileSync(new URL('../src/views/portal/components/PortalUserAvatar.vue', import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: 'avatar-display-test' })
  const store = vue.reactive({ avatar: '/default.png', nickName: '年糕' })
  const code = script.content.replace(/^import[^\n]*\n/gm, '').replace('export default', 'return')
  const component = new Function('computed', 'ref', 'watch', 'useUserStore', 'defaultAvatar', code)(vue.computed, vue.ref, vue.watch, () => store, '/default.png')
  const display = component.setup({}, { expose() {} })
  assert.equal(display.src.value, '')
  assert.equal(display.initial.value, '年')
  display.failed.value = true
  store.avatar = '/dev-api/profile/avatar/new.png'
  await vue.nextTick()
  assert.equal(display.src.value, store.avatar)
  assert.equal(display.failed.value, false)
})

test('cancel clears local preview without upload and rejects invalid files', async () => {
  let calls = 0
  const ctx = await mountEditor(async () => { calls += 1 })
  try {
    ctx.page.clearDraft()
    await ctx.page.saveAvatar()
    assert.equal(ctx.page.source.value, '')
    assert.equal(ctx.page.ready.value, false)
    assert.equal(ctx.store.avatar, '/old.png')
    ctx.page.chooseImage({ raw: { type: 'text/plain', size: 100 } })
    assert.ok(ctx.page.error.value)
    assert.equal(ctx.page.source.value, '')
    assert.equal(calls, 0)
  } finally { ctx.close() }
})
