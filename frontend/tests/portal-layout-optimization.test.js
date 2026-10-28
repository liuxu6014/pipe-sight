import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
const read = name => readFileSync(new URL(`../src/views/portal/pages/${name}.vue`, import.meta.url), 'utf8')
test('material information does not invent references or chunk counts', () => {
  assert.doesNotMatch(read('KnowledgeDetailView'), /引用记录|切块结果|chunks.length|尚未被报告或简报引用/)
})
test('private uploads offer only supported fields and a compact list', () => {
  const source = read('KnowledgeView')
  assert.doesNotMatch(source, /value="public"|v-model="uploadCategory"|v-model="uploadPermission"|页数待补充|ps-knowledge-status-strip/)
  assert.match(source, /class="ps-material-list"/)
  assert.match(source, /data.append\('permissionScope', 'private'\)/)
})
test('all changed reading templates compile with existing Vue bindings', () => {
  for (const name of ['KnowledgeView', 'KnowledgeDetailView', 'NewsDetailView', 'PaperDetailView', 'PaperListView', 'SearchView']) {
    const { descriptor } = parse(read(name))
    const script = compileScript(descriptor, { id: name })
    const result = compileTemplate({ source: descriptor.template.content, filename: `${name}.vue`, id: name, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [], name)
  }
})
