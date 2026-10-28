import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/portal/pages/ResearchTaskView.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const has = (node, name) => node.props?.find(p => p.name === 'class')?.value?.content.split(' ').includes(name)

test('task toolbar and actions stay outside the independently scrolling details', () => {
  const found = new Set()
  function walk(node, scrolling = false) {
    for (const name of ['ps-task-toolbar', 'ps-task-footer']) if (has(node, name)) {
      assert.equal(scrolling, false)
      found.add(name)
    }
    for (const child of node.children || []) walk(child, scrolling || has(node, 'ps-task-scroll'))
  }
  walk(descriptor.template.ast)
  assert.equal(found.size, 2)
  assert.match(source, /\.ps-task-scroll \{[^}]*min-height: 0[^}]*overflow-y: auto/)
  assert.match(source, /@media \(max-width: 900px\)/)
  assert.match(source, /@media \(max-width: 560px\)/)
})

test('stages and event log share one main column without spanning empty grid rows', () => {
  function find(node) {
    if (has(node, 'ps-task-main')) return node
    return (node.children || []).map(find).find(Boolean)
  }
  const main = find(descriptor.template.ast)
  assert.ok(main.children.some(node => has(node, 'ps-task-timeline')))
  assert.ok(main.children.some(node => has(node, 'ps-task-log')))
  assert.doesNotMatch(source, /class="ps-task-hero"|class="ps-sticky-actions"/)
  assert.match(source, /task\.applyConflict[^>]*type="info"/)
})

test('task view compiles with the existing Element Plus controls and unchanged action guards', () => {
  const script = compileScript(descriptor, { id: 'task-layout' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'ResearchTaskView.vue',
    id: 'task-layout', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.match(source, /:disabled="!canOpenReport" @click="openReport"/)
  assert.match(source, /v-if="canCancel"/)
  assert.match(source, /v-else-if="canRetry"/)
})
