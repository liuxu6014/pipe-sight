import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const page = read('../src/views/pipeline/knowledge/index.vue')
const api = read('../src/api/pipeline/intelligence.js')

test('connects management knowledge uploads to the real material lifecycle APIs', () => {
  for (const apiName of [
    'listPipelineKnowledgeDocuments',
    'uploadPipelineKnowledgeDocument',
    'reparsePipelineKnowledgeDocument',
    'deletePipelineKnowledgeDocument'
  ]) {
    assert.match(api, new RegExp(`export function ${apiName}`))
    assert.match(page, new RegExp(apiName))
  }

  assert.match(page, /permissionScope/)
  assert.match(page, /MAX_FILE_SIZE = 100 \* 1024 \* 1024/)
  assert.match(page, /ALLOWED_EXTENSIONS/)
  assert.match(page, /ElMessageBox\.confirm/)
  assert.doesNotMatch(page, /showUploadTodo|后续接 MinIO|将在生产版接入/)
})

test('uses the controlled download endpoint for authorized documents', () => {
  assert.match(api, /downloadPipelineKnowledgeDocument/)
  assert.match(page, /downloadPipelineKnowledgeDocument\(document\.id/)
  assert.match(page, /row\.allowDownload === false/)
})

test('provides loading, error, empty, pagination and responsive states', () => {
  assert.match(page, /loadError/)
  assert.match(page, /el-empty/)
  assert.match(page, /el-pagination/)
  assert.match(page, /uploading\.value/)
  assert.match(page, /@media \(max-width: 760px\)/)
})
