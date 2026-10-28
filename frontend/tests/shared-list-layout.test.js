import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const read = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const portals = ['NewsListView', 'PaperListView', 'ResearchWorkbenchView', 'DigestListView', 'SearchView', 'MyReportsView', 'MyWorkspaceView']
const management = ['intelligence', 'source', 'task', 'knowledge', 'report', 'template']
test('portal and business management lists opt into the shared viewport layout', () => {
  for (const page of portals) assert.match(read(`views/portal/pages/${page}.vue`), /ps-list-page/, page)
  for (const page of management) assert.match(read(`views/pipeline/${page}/index.vue`), /ws-list-page/, page)
  for (const page of ['ResearchCreateView', 'ReportEditorView', 'KnowledgeDetailView']) {
    assert.doesNotMatch(read(`views/portal/pages/${page}.vue`), /ps-list-page/, page)
  }
})
test('pagination remains outside each independently scrolling region', () => {
  for (const page of ['NewsListView', 'PaperListView', 'ResearchWorkbenchView', 'SearchView']) {
    const { descriptor } = parse(read(`views/portal/pages/${page}.vue`))
    function walk(node, insideScroll = false) {
      const classProp = node.props?.find(prop => prop.name === 'class')
      const classText = classProp?.value?.content || classProp?.exp?.content || ''
      if (/ps-pagination/.test(classText)) assert.equal(insideScroll, false, page)
      const scrolling = insideScroll || /ps-list-scroll/.test(classText)
      for (const child of node.children || []) walk(child, scrolling)
    }
    walk(descriptor.template.ast)
  }
})
test('changed templates compile without missing or invalid bindings', () => {
  const paths = [...portals.map(p => `views/portal/pages/${p}.vue`), ...management.map(p => `views/pipeline/${p}/index.vue`)]
  for (const filename of paths) {
    const { descriptor } = parse(read(filename))
    const script = compileScript(descriptor, { id: filename })
    const compiled = compileTemplate({ source: descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(compiled.errors, [], filename)
  }
})
test('shared shell bounds list height, preserves controls and handles small windows', () => {
  const styles = read('assets/styles/workspace.scss')
  assert.match(styles, /\.ps-list-scroll \{ flex: 1 1 0; min-height: 0; min-width: 0; overflow: auto/)
  assert.match(styles, /\.ps-list-stack \{ display: flex; flex-direction: column; align-items: stretch; width: 100%/)
  assert.match(styles, /\.ws-list-panel > \.el-card__body \{ flex: 1 1 0; min-height: 0; display: flex/)
  assert.match(styles, /\.pagination-container, \.knowledge-pagination \{ flex-shrink: 0/)
  assert.match(styles, /@media \(max-height: 640px\)/)
  assert.match(styles, /align-items: stretch; grid-template-rows: minmax\(0, 1fr\)/)
  assert.match(styles, /> \.ps-toolbar \{ flex-direction: row; flex-wrap: wrap/)
  assert.match(styles, /\.ps-pagination \.el-pagination__jump \{ display: none/)
})
