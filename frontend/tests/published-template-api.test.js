import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('portal published-template queries use the read-only endpoint, management queries do not', () => {
  const source = readFileSync(new URL('../src/api/pipeline/intelligence.js', import.meta.url), 'utf8')
  const action = source.slice(source.indexOf('export function listPipelineTemplates'), source.indexOf('export function createPipelineTemplate'))
    .replace('export function', 'function')
  const context = vm.createContext({ request: options => options })
  vm.runInContext(action, context)
  assert.equal(context.listPipelineTemplates({ publishedOnly: true, category: 'research' }).url, '/pipeline/templates/published')
  assert.equal(context.listPipelineTemplates({ publishedOnly: false }).url, '/pipeline/templates')
  assert.equal(context.listPipelineTemplates().url, '/pipeline/templates')
})
