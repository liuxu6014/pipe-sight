import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
const home = readFileSync(new URL('../src/views/portal/pages/HomeView.vue', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')

test('home keeps search, metrics, shortcuts and the latest feed in a viewport shell', () => {
  assert.match(home, /ps-home-dashboard ps-home-viewport/)
  for (const section of ['ps-home-search-panel', 'ps-home-statistics', 'ps-home-modules', 'ps-home-latest']) assert.match(home, new RegExp(section))
  assert.match(styles, /\.ps-portal-main:has\(> \.ps-home-viewport\)/)
  assert.match(styles, /\.ps-home-dashboard\.ps-home-viewport \{[\s\S]*?max-width: none/)
  assert.match(styles, /@media \(max-width: 1100px\), \(max-height: 700px\)/)
  assert.match(styles, /grid-template-rows: auto auto auto minmax\(0, 1fr\)/)
})
test('results and latest feed scroll without moving their headers or search pagination', () => {
  const { descriptor } = parse(home)
  let panels = 0
  function walk(node, scrolling = false) {
    const classes = node.props?.find(p => p.name === 'class')?.value?.content || ''
    if (classes.includes('ps-home-panel-content')) panels++
    if (classes.includes('ps-pagination') || classes.includes('ps-section-head')) assert.equal(scrolling, false)
    for (const child of node.children || []) walk(child, scrolling || classes.includes('ps-home-panel-content'))
  }
  walk(descriptor.template.ast)
  assert.equal(panels, 2)
  assert.match(styles, /\.ps-home-panel-content \{ flex: 1 1 0; min-height: 0; min-width: 0; overflow: auto/)
  const script = compileScript(descriptor, { id: 'home-flex' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'HomeView.vue', id: 'home-flex', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
})
