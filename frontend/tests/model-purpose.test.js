import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, reactive } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { modelsFor } from '../src/utils/pipeline/compactContract.js'
const source = readFileSync(new URL('../src/views/pipeline/model/components/ModelPurposeSettings.vue', import.meta.url), 'utf8')
function setup(overrides = {}) {
 const writes = []
 const dependencies = { computed, reactive, onMounted() {}, defineEmits() {}, defineProps: () => ({ models: [
  { modelId: '90071992547409931', modelName: '文本模型', capabilities: ['text_generate'], status: '0' },
  { modelId: '2', capabilities: ['image_generate'], status: '0' },
  { modelId: '3', capabilities: ['text_generate'], status: '1' }
 ], editable: true }), modelsFor, ElMessage: { success() {} },
 getProcessingModelConfig: async () => ({ data: { modelId: null } }),
 getTranslationModelConfig: async () => ({ data: { modelId: null } }),
 getGenerationModelConfig: async () => ({ data: { modelId: null } }),
 updateGenerationModelConfig: async (purpose, value) => writes.push([purpose, value]),
 updateProcessingModelConfig: async value => writes.push(['processing', value]),
 updateTranslationModelConfig: async value => writes.push(['translation', value]), ...overrides }
 const script = parse(source).descriptor.scriptSetup.content.replace(/^import .*\n/gm, '')
 return { ...new Function(...Object.keys(dependencies), `${script}\nreturn { purposes, load, save, unavailable, availableModels }`)(...Object.values(dependencies)), writes }
}
test('five independently saved purposes never auto-select a model', async () => {
 const h = setup(); await Promise.all(h.purposes.map(h.load))
 assert.deepEqual(h.purposes.map(item => item.modelId), ['', '', '', '', '']); assert.deepEqual(h.writes, [])
 h.purposes[0].modelId = '90071992547409931'; await h.save(h.purposes[0])
 assert.deepEqual(h.writes, [['processing', { modelId: '90071992547409931' }]])
 assert.equal(h.purposes[1].modelId, '')
 h.purposes[1].modelId = '90071992547409931'; await h.save(h.purposes[1])
 h.purposes[0].modelId = ''; await h.save(h.purposes[0])
 assert.deepEqual(h.writes[2], ['processing', { modelId: null }])
 assert.equal(h.purposes[1].savedId, '90071992547409931')
})
test('unavailable models and failed reads cannot be saved; one failing purpose leaves the other usable', async () => {
 const h = setup({ getProcessingModelConfig: async () => { throw new Error('读取失败') } })
 await Promise.all(h.purposes.map(h.load))
 const [processing, translation] = h.purposes
 processing.modelId = '90071992547409931'; await h.save(processing); assert.equal(h.writes.length, 0)
 for (const id of ['2', '3', '4']) { translation.modelId = id; await h.save(translation); assert.match(translation.saveError, /已启用/) }
 translation.modelId = '90071992547409931'; await h.save(translation)
 assert.equal(h.writes.length, 1); assert.equal(h.writes[0][0], 'translation')
})
test('duplicate writes and unauthorized edits are blocked; a failed save retains the draft', async () => {
 let finish, calls = 0
 const h = setup({ updateProcessingModelConfig: async () => { calls++; await new Promise(resolve => { finish = resolve }); throw new Error('保存失败') } })
 await h.load(h.purposes[0]); h.purposes[0].modelId = '90071992547409931'
 const pending = h.save(h.purposes[0]); await h.save(h.purposes[0]); assert.equal(calls, 1)
 finish(); await pending
 assert.equal(h.purposes[0].savedId, ''); assert.equal(h.purposes[0].modelId, '90071992547409931'); assert.equal(h.purposes[0].saveError, '保存失败')
 const denied = setup({ defineProps: () => ({ editable: false, models: [] }) }); await denied.load(denied.purposes[0]); denied.purposes[0].modelId = '1'; await denied.save(denied.purposes[0]); assert.deepEqual(denied.writes, [])
})
test('purpose component compiles with Element Plus selects and buttons', () => {
 const descriptor = parse(source).descriptor
 const script = compileScript(descriptor, { id: 'purpose' })
 const template = compileTemplate({ source: descriptor.template.content, filename: 'ModelPurposeSettings.vue', id: 'purpose', compilerOptions: { bindingMetadata: script.bindings } })
 assert.deepEqual(template.errors, []); assert.match(source, /过滤、分类时一并生成摘要、提取实体/)
})

test('route validation messages remain a retryable Chinese error without enabling stale saves', async () => {
 let unavailable = true
 const h = setup({ getProcessingModelConfig: async () => {
  if (unavailable) throw new Error('Input should be a valid integer, unable to parse string as an integer')
  return { data: { modelId: null } }
 } })
 const item = h.purposes[0]
 await h.load(item)
 assert.match(item.error, /内容处理模型读取失败/)
 assert.doesNotMatch(item.error, /integer/)
 item.modelId = '90071992547409931'; await h.save(item); assert.deepEqual(h.writes, [])
 unavailable = false; await h.load(item)
 assert.equal(item.error, ''); assert.equal(item.modelId, '')
})

test('image generation, brief and research purposes save independently with matching capabilities', async () => {
 const h = setup(); await Promise.all(h.purposes.map(h.load))
 const image = h.purposes.find(item => item.key === 'image')
 assert.deepEqual(h.availableModels(image).map(model => model.modelId), ['2'])
 image.modelId = '90071992547409931'; await h.save(image)
 assert.match(image.saveError, /图片生成/); assert.deepEqual(h.writes, [])
 image.modelId = '2'; await h.save(image)
 assert.deepEqual(h.writes[0], ['image', { modelId: '2' }])
 for (const purpose of ['digest', 'research']) {
  const item = h.purposes.find(item => item.key === purpose)
  assert.deepEqual(h.availableModels(item).map(model => model.modelId), ['90071992547409931'])
  item.modelId = '90071992547409931'; await h.save(item)
  assert.deepEqual(h.writes.at(-1), [purpose, { modelId: '90071992547409931' }])
 }
 assert.equal(h.purposes[0].savedId, ''); assert.equal(h.purposes[1].savedId, '')
})
