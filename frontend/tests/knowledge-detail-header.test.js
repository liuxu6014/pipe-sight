import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/portal/pages/KnowledgeDetailView.vue', import.meta.url), 'utf8')

test('reader prioritizes continuous text with optional information instead of fake pages and permanent rails', () => {
  assert.doesNotMatch(source, /class="ps-document-nav"|ps-preview-page-number|页数待补充|const versions =/)
  assert.match(source, /const showInfo = ref\(false\)/)
  assert.match(source, /v-if="showInfo" id="material-info"/)
  assert.match(source, /:aria-expanded="showInfo" aria-controls="material-info"/)
  assert.match(source, /v-if="chapters.length > 1" v-model="activeChapter"/)
  assert.match(source, /height: max\(360px, calc\(100dvh - 220px\)\)/)
  assert.match(source, /min-height: 0; overflow: auto/)
  assert.match(source, /font-size: calc\(16px \* var\(--ps-preview-zoom, 1\)\)/)
})

test('document header emphasizes filename and omits duplicate summary and ownership fields', () => {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'knowledge-header' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'KnowledgeDetailView.vue', id: 'knowledge-header', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  const header = source.split('<section class="ps-document-detail-head">')[1].split('</section>')[0]
  assert.match(header, /<h1 v-else>{{ document.name }}<\/h1>/)
  assert.doesNotMatch(header, /加入资料库|isInBasket/)
  assert.match(header, /v-if="document.allowDownload !== false"/)
  assert.match(header, /v-if="canManage" trigger="click"/)
  assert.match(header, /:disabled="loading \|\| !liveDocument" :icon="Edit"/)
  assert.doesNotMatch(header, /document.summary|上传人|所有者|页数待补充|ps-doc-type|document.permission/)
})

test('material edits happen inline with a filename field and top-level save controls, not a dialog', () => {
  assert.doesNotMatch(source, /<el-dialog/)
  assert.match(source, /<el-input v-if="editVisible" v-model="editDraft.name"/)
  assert.match(source, /<section v-if="editVisible" class="ps-material-inline-editor"/)
  assert.match(source, /v-model="editDraft.text" aria-label="资料正文"/)
  assert.match(source, /:loading="editSaving" @click="saveEdits">保存修改/)
  assert.match(source, /:disabled="editSaving" @click="cancelEditing">取消/)
  assert.match(source, /onBeforeRouteLeave\(protectEdits\)/)
})

test('uploaded material already belongs to the unified library and needs no second add action', () => {
  assert.doesNotMatch(source, /加入资料库|addToBasket|isInBasket/)
  assert.match(source, /route.query.mode === 'edit'/)
  assert.match(source, /router.replace\('\/portal\/basket'\)/)
})
