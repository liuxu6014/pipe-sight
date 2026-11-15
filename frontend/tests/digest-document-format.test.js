import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { buildReportMarkdown, cleanReportCitationNotes, reportCitationParts } from '../src/utils/portal/reportDocument.js'
import { digestMasthead, digestPeriodLabel } from '../src/utils/portal/digestDocument.js'
import { cleanSource } from '../src/utils/portal/discovery.js'

test('the digest header shows a generated masthead and a single localized period, preserving custom titles', () => {
  const period = ['2025-04-01', '2025-04-30']
  assert.equal(digestMasthead('管网科技情报月报 2025年4月', period), '管网科技情报月报')
  assert.equal(digestMasthead('管网科技情报月报 2025年4月 · 检测专题', period), '管网科技情报月报 2025年4月 · 检测专题')
  assert.equal(digestPeriodLabel(period), '2025年4月1日到4月30日')
  assert.equal(digestPeriodLabel(['2025-12-29', '2026-01-04']), '2025年12月29日到2026年1月4日')
})

test('digest sources stay below their own event with local numbering and no duplicate title or bibliography', () => {
  const content = '### 1. 检测技术进展\n\n事实摘要。\n\n行业洞察：尚需验证。\n\n数据源：\n\n[1] [标题【来源】](https://example.org/news)'
  const output = buildReportMarkdown({ title: '周报', sections: [{ title: '油气管网', content }], citations: [{ title: '其他来源', sourceId: '99', id: 3 }], documentFormat: 'digest-reference-v1' })
  assert.equal(output, '**油气管网**\n\n' + content)
  assert.equal(cleanReportCitationNotes(output), output)
  assert.deepEqual(reportCitationParts('[1] [标题【来源】](https://example.org/news)', '油气管网', 3), [{ text: '[1] [标题【来源】](https://example.org/news)', citation: false }])
})

test('digest reading and editing component uses semantic headings and preserves role prefixes', () => {
  const source = readFileSync(new URL('../src/views/portal/components/DigestSectionContent.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'digest-content' })
  const template = compileTemplate({ source: descriptor.template.content, id: 'digest-content', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  assert.match(source, /syncContent/)
  assert.match(source, /data-role="event"/)
  assert.match(source, /noopener noreferrer/)
  assert.doesNotMatch(source, /v-html/)
})

test('saved digest source labels are clean when reading while editing retains original text and URL', () => {
  const source = readFileSync(new URL('../src/views/portal/components/DigestSectionContent.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const label = '检测进展【新华网（国家管网官网转载）】'
  const url = 'https://example.org/官网转载?original=1'
  const props = { content: `[1] [${label}](${url})`, editable: false }
  const emitted = []
  const setup = descriptor.scriptSetup.content.replace(/^import[^\n]*\n/gm, '')
  const page = new Function('computed', 'ref', 'defineProps', 'defineEmits', 'cleanSource',
    `${setup}\nreturn { blocks, contentElement, syncContent }`)(vue.computed, vue.ref, () => props, () => (...args) => emitted.push(args), cleanSource)
  const template = compileTemplate({ source: descriptor.template.content, id: 'digest-display', compilerOptions: { mode: 'function' } })
  assert.deepEqual(template.errors, [])
  const render = new Function('Vue', template.code)({ ...vue, resolveDirective: () => ({}), withDirectives: node => node })
  const anchors = node => !node || typeof node !== 'object' ? [] : [
    ...(node.type === 'a' ? [node] : []), ...(Array.isArray(node.children) ? node.children.flatMap(anchors) : [])
  ]
  const readLink = anchors(render({ blocks: page.blocks.value, editable: false, cleanSource }, []))[0]
  assert.equal(readLink.children, '检测进展【新华网】')
  assert.equal(readLink.props.href, url)
  const editLink = anchors(render({ blocks: page.blocks.value, editable: true, cleanSource }, []))[0]
  assert.equal(editLink.children, label)
  assert.equal(editLink.props.href, url)
  props.editable = true
  page.contentElement.value = { children: [{ innerText: `[1] ${label}`, dataset: { role: 'source', number: '[1]', url } }] }
  page.syncContent({ isComposing: false })
  assert.deepEqual(emitted, [['update:content', props.content]])
})
