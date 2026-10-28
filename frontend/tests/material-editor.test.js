import test from 'node:test'
import assert from 'node:assert/strict'
import { useMaterialEditor } from '../src/utils/portal/materialEditor.js'

const doc = () => ({ id: '54', name: '资料.docx', versionNo: 3, canManage: true, editedText: null, extractedText: '原始提取正文' })

test('material editor distinguishes changed drafts and blocks leaving while saving', async () => {
  let resolve
  const editor = useMaterialEditor({ update: () => new Promise(done => { resolve = done }) })
  editor.open(doc())
  assert.equal(editor.dirty.value, false)
  editor.draft.text = '未保存改动'
  assert.equal(editor.dirty.value, true)
  const saving = editor.save()
  assert.equal(editor.saving.value, true)
  assert.equal(await editor.canLeave(async () => true), false)
  resolve({ data: { ...doc(), editedText: '未保存改动' } })
  await saving
  assert.equal(editor.dirty.value, false)
  editor.open(doc())
  editor.draft.name = '新标题'
  assert.equal(await editor.canLeave(async () => false), false)
  assert.equal(await editor.canLeave(async () => true), true)
})

test('material editing sends the frozen version and text without changing the original file', async () => {
  const calls = [], saved = []
  const editor = useMaterialEditor({ update: async (...args) => { calls.push(args); return { data: { ...doc(), name: args[1].name, editedText: args[1].editedText, versionNo: 4 } } }, onSaved: item => saved.push(item) })
  const original = doc()
  assert.equal(editor.open(original), true)
  assert.equal(editor.draft.text, '原始提取正文')
  editor.draft.name = ' 修订资料.docx '
  editor.draft.text = '修订后的正文'
  assert.equal(await editor.save(), true)
  assert.deepEqual(calls, [['54', { expectedVersion: 3, name: '修订资料.docx', editedText: '修订后的正文' }]])
  assert.equal(original.editedText, null)
  assert.equal(original.extractedText, '原始提取正文')
  assert.equal(saved[0].versionNo, 4)
  assert.equal(editor.visible.value, false)
})

test('version conflicts and network failures keep the draft open and unchanged', async () => {
  const editor = useMaterialEditor({ update: async () => { throw { msg: '版本已变化，请重新加载' } }, onSaved: () => assert.fail('must not replace document') })
  editor.open(doc())
  editor.draft.text = '未保存的人工修改'
  assert.equal(await editor.save(), false)
  assert.equal(editor.visible.value, true)
  assert.equal(editor.draft.text, '未保存的人工修改')
  assert.equal(editor.draft.version, 3)
  assert.match(editor.error.value, /版本已变化/)
  assert.equal(editor.saving.value, false)
})

test('read-only documents and invalid edits cannot call the update API', async () => {
  let calls = 0
  const editor = useMaterialEditor({ update: async () => { calls++ } })
  assert.equal(editor.open({ ...doc(), canManage: false }), false)
  assert.equal(editor.open({ ...doc(), canManage: undefined }), false)
  assert.equal(editor.open({ id: '54', name: '仅列表缓存.docx', canManage: true, versionNo: 3 }), false)
  assert.equal(await editor.save(), false)
  editor.open(doc())
  editor.draft.name = '  '
  assert.equal(await editor.save(), false)
  assert.equal(calls, 0)
})
