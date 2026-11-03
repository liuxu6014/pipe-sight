import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileStyle, compileTemplate } from '@vue/compiler-sfc'

const read = name => readFileSync(new URL(`../src/views/portal/${name}.vue`, import.meta.url), 'utf8')
const news = read('pages/NewsListView')
const entities = read('components/ContentEntities')

test('news keeps saved conditions in its toolbar without the current-filter row', () => {
  const { descriptor } = parse(news)
  const page = descriptor.template.ast.children.find(node => node.type === 1)
  const toolbar = page.children.find(node => node.type === 1 && node.props.some(p => p.name === 'class' && p.value?.content === 'ps-toolbar'))
  const saved = toolbar.children.find(node => node.type === 1 && node.tag === 'SavedSearchBar')
  assert.ok(saved)
  assert.ok(saved.props.some(p => p.arg?.content === 'show-current-filters' && p.exp?.content === 'false'))
  assert.equal(page.children.some(node => node.type === 1 && node.tag === 'SavedSearchBar'), false)
  assert.match(read('components/SavedSearchBar'), /v-if="showCurrentFilters" class="ps-query-chips"/)
})

test('stored entities use native small tags with category colors, without fake empty tags', () => {
  assert.match(entities, /<el-tag[^>]*:type="tagTypes\[group.label\]" size="small"/)
  assert.match(entities, /地点: 'primary'.*时间: 'info'.*政策: 'warning'.*人物: 'danger'.*机构: 'success'.*技术: 'primary'/)
})

test('article metadata and the bordered saved-item control share a compact heading instead of a separate footer', () => {
  const markup = parse(news).descriptor.template.content
  assert.match(markup, /class="ps-news-row-heading"/)
  assert.match(markup, /class="ps-news-source" :title="item.source"/)
  assert.match(markup, /class="ps-news-categories"><el-button/)
  assert.match(markup, /class="ps-news-row-actions"><el-button type="primary" plain/)
  assert.doesNotMatch(markup, /ps-news-card-footer/)
  assert.match(markup, /v-if="cleanSummary\(item.summary\)" class="ps-news-summary"/)
  assert.match(news, /\.ps-news-page \.ps-news-list \{[^}]*align-content: start/)
})

test('compact entity views omit the entire empty section but retain the honest detail empty state', () => {
  const markup = parse(entities).descriptor.template.content
  assert.match(markup, /v-if="!compact \|\| hasEntities"/)
  assert.doesNotMatch(markup, /实体信息待处理|v-if="compact && !hasEntities"/)
  assert.match(markup, /v-if="!compact && !hasEntities"/)
  assert.match(entities, /\.is-compact \{[^}]*background: transparent/)
})

test('compact news and entity templates, scoped styles and scripts compile', () => {
  for (const [filename, source] of [['NewsListView.vue', news], ['ContentEntities.vue', entities]]) {
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, filename, id: filename, scoped: true }).errors, [])
  }
})
