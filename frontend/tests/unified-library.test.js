import test from 'node:test'
import assert from 'node:assert/strict'
import { buildLibraryItems, libraryItemPath, libraryItemReason, prepareLibrarySelection } from '../src/utils/portal/libraryItems.js'

test('library merges uploads and saved sources once per resource, with live file permissions', () => {
  const rows = buildLibraryItems([
    { id: '54', type: 'material', title: '旧标题', status: '已解析' },
    { id: '18', type: 'article', title: '新闻' }, { id: '18', type: 'article', title: '重复' },
    { id: '26', type: 'paper', title: '论文' }, { id: '99', type: 'material', title: '已删除资料' }
  ], [{ id: '54', name: '修订标题', status: '解析失败', canManage: true }])
  assert.equal(rows.length, 3)
  assert.equal(rows.find(row => row.id === '54').name, '修订标题')
  assert.match(libraryItemReason(rows.find(row => row.id === '54')), /解析/)
  assert.deepEqual(rows.map(libraryItemPath).sort(), ['/portal/knowledge/54', '/portal/news/18', '/portal/papers/26'])
})
test('different resource IDs sharing a filename are not wrongly collapsed', () => {
  assert.equal(buildLibraryItems([], [{ id: '1', name: '报告.docx' }, { id: '2', name: '报告.docx' }]).length, 2)
})
test('file bytes identify duplicates regardless of filename, without merging distinct contents or edits', () => {
  const hash = 'a'.repeat(64)
  const rows = buildLibraryItems([], [
    { id: '50', name: 'a.txt', fileHash: hash, ownerId: 7, status: '已解析' },
    { id: '49', name: '改名.txt', fileHash: hash, ownerId: 7, status: '已解析' },
    { id: '51', name: 'a.txt', fileHash: 'b'.repeat(64), ownerId: 7, status: '已解析' },
    { id: '52', name: 'a.txt', fileHash: hash, editHash: 'c'.repeat(64), ownerId: 7, status: '已解析' }
  ])
  assert.equal(rows.length, 3)
  assert.deepEqual(rows[0].duplicateIds, ['49', '50'])
  assert.equal(rows[0].id, '49')
})
test('generation saves missing uploads before navigation and does not truncate over-limit selections', async () => {
  const saved = []
  const rows = [{ id: '54', kind: 'document', status: '已解析', name: '资料' }, { id: '26', kind: 'paper', name: '论文' }]
  const result = await prepareLibrarySelection(rows, async (item, type) => { saved.push([item.id, type]); return 'saved' })
  assert.deepEqual(result, ['54', '26'])
  assert.deepEqual(saved, [['54', 'material'], ['26', 'paper']])
  saved.length = 0
  await assert.rejects(prepareLibrarySelection(Array.from({ length: 51 }, (_, i) => ({ id: String(i + 1), kind: 'paper' })), async () => saved.push('unexpected')), /50/)
  assert.equal(saved.length, 0)
})
test('unusable uploads and failed persistence stop generation explicitly', async () => {
  await assert.rejects(prepareLibrarySelection([{ id: '54', kind: 'document', status: '解析中' }], async () => 'saved'), /解析/)
  await assert.rejects(prepareLibrarySelection([{ id: '54', kind: 'paper' }], async () => 'stale'), /保存/)
})
