import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { reactive, ref } from 'vue'

function setup({ valid = true, update = async () => {} } = {}) {
  const events = []
  const { descriptor } = parse(readFileSync(new URL('../src/views/system/user/profile/resetPwd.vue', import.meta.url), 'utf8'))
  const source = compileScript(descriptor, { id: 'password-reset' }).content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '')
    .replace('export default', 'return')
  const proxy = {
    $refs: { pwdRef: { validate: async () => { if (!valid) throw new Error('invalid form'); return true } } },
    $modal: { msgSuccess: message => events.push(['success', message]), msgError: message => events.push(['error', message]) },
    $tab: { closePage() {} }
  }
  const component = new Function('getCurrentInstance', 'reactive', 'ref', 'useUserStore', 'useRouter', 'updateUserPwd', source)(
    () => ({ proxy }), reactive, ref,
    () => ({ logOut: async () => events.push(['logout']) }),
    () => ({ replace: async path => events.push(['route', path]) }),
    async (...args) => { events.push(['update', ...args]); return update(...args) }
  )
  const bindings = component.setup({}, { expose() {} })
  bindings.user.oldPassword = 'OldPassword12'
  bindings.user.newPassword = 'NewPassword12'
  return { bindings, events }
}

test('successful password change ends the old local session and opens login', async () => {
  const { bindings, events } = setup()
  await bindings.submit()
  assert.deepEqual(events, [
    ['update', 'OldPassword12', 'NewPassword12'],
    ['success', '密码修改成功，请重新登录'],
    ['logout'], ['route', '/login']
  ])
  assert.equal(bindings.saving.value, false)
})

test('invalid form and rejected old password keep the session and form intact', async () => {
  const invalid = setup({ valid: false })
  await invalid.bindings.submit()
  assert.deepEqual(invalid.events, [])
  const rejected = setup({ update: async () => { throw new Error('旧密码错误') } })
  await rejected.bindings.submit()
  assert.deepEqual(rejected.events, [['update', 'OldPassword12', 'NewPassword12'], ['error', '旧密码错误']])
  assert.equal(rejected.bindings.saving.value, false)
  assert.equal(rejected.bindings.user.oldPassword, 'OldPassword12')
})

test('double submit while a password change is pending sends only one request', async () => {
  let complete
  const waiting = new Promise(resolve => { complete = resolve })
  const { bindings, events } = setup({ update: () => waiting })
  const first = bindings.submit()
  await Promise.resolve()
  await Promise.resolve()
  const second = bindings.submit()
  complete()
  await Promise.all([first, second])
  assert.equal(events.filter(item => item[0] === 'update').length, 1)
  assert.equal(events.filter(item => item[0] === 'logout').length, 1)
})
