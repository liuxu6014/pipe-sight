import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { ref } from 'vue'

const source = readFileSync(new URL('../src/views/portal/pages/MyWorkspaceView.vue', import.meta.url), 'utf8')
function setup(confirm) {
  const calls = [], messages = []
  const store = { workspaceEpoch: 1, removeFromBasket: async id => { calls.push(id); return true } }
  const match = source.match(/async function deleteBasketItem\(item\) \{[\s\S]*?\n\}/)
  assert.ok(match, 'basket delete handler exists')
  const context = vm.createContext({ deletingBasketId: ref(''), basketDeleteActive: true, portalStore: store,
    ElMessageBox: { confirm }, ElMessage: { success: message => messages.push(message), error: message => messages.push(message) } })
  vm.runInContext(`${match[0]}\nglobalThis.remove = deleteBasketItem`, context)
  return { store, calls, messages, remove: context.remove }
}
test('cancelled confirmation never deletes a basket entry', async () => {
  const view = setup(async message => { assert.match(message, /测试资料/); throw 'cancel' })
  await view.remove({ id: '50', title: '测试资料' })
  assert.equal(view.calls.length, 0)
  assert.equal(view.messages.length, 0)
})
test('confirmation gates deletion, duplicate clicks and account switches are safe', async () => {
  let accept
  const view = setup(() => new Promise(resolve => { accept = resolve }))
  const pending = view.remove({ id: '50', title: '测试资料' })
  await view.remove({ id: '50', title: '测试资料' })
  assert.equal(view.calls.length, 0)
  accept()
  await pending
  assert.deepEqual(view.calls, ['50'])
  assert.equal(view.messages.length, 1)
  const stale = view.remove({ id: '50', title: '测试资料' })
  view.store.workspaceEpoch++
  accept()
  await stale
  assert.equal(view.calls.length, 1)
})
