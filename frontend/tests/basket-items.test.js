import test from 'node:test'
import assert from 'node:assert/strict'
import { basketItemPath, basketItemLabel, validateBasketUpload, uploadBasketFile } from '../src/utils/portal/basketItems.js'

test('basket uses source record IDs and routes papers/news/files to their own details', () => {
  for (const [type, path, label] of [['paper', 'papers', '论文'], ['article', 'news', '新闻资讯'], ['file', 'knowledge', '上传资料'], ['material', 'knowledge', '上传资料']]) {
    assert.equal(basketItemPath({ id: '26', type }), `/portal/${path}/26`)
    assert.equal(basketItemLabel({ id: '26', type }), label)
  }
  assert.equal(basketItemPath({ id: 'bad', type: 'paper' }), null)
})

test('upload validates type, empty files and size', () => {
  assert.ok(validateBasketUpload({ name: 'a.exe', size: 1 }))
  assert.ok(validateBasketUpload({ name: 'a.txt', size: 0 }))
  assert.ok(validateBasketUpload({ name: 'a.pdf', size: 16 * 1024 * 1024 + 1 }))
  assert.equal(validateBasketUpload({ name: 'a.TXT', size: 100 }), '')
})

test('upload persists to library before saving a basket foreign key and refreshing', async () => {
  const calls = []
  const result = await uploadBasketFile(new File(['test'], 'sample.txt'), {
    upload: async data => { calls.push('library'); assert.equal(data.get('permissionScope'), 'private'); assert.equal(await data.get('file').text(), 'test'); return { data: { id: '99' } } },
    save: async item => { calls.push('basket'); assert.deepEqual(item, { itemId: '99', itemType: 'material', action: 'basket', title: 'sample.txt' }) },
    refresh: async () => calls.push('refresh')
  })
  assert.deepEqual(calls, ['library', 'basket', 'refresh'])
  assert.deepEqual(result, { id: '99', basketError: false })
})

test('failed library upload never adds a basket item; basket failure reports already saved file', async () => {
  let saved = false
  await assert.rejects(uploadBasketFile(new File(['x'], 'a.txt'), { upload: async () => { throw new Error('failed') }, save: async () => { saved = true } }), /failed/)
  assert.equal(saved, false)
  const result = await uploadBasketFile(new File(['x'], 'a.txt'), { upload: async () => ({ data: { id: '99' } }), save: async () => { throw new Error('failed') }, refresh: async () => {} })
  assert.equal(result.basketError, true)
})
