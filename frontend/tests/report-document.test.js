import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, effectScope, ref, watch } from 'vue'
import { buildReportMarkdown, cleanReportCitationNotes } from '../src/utils/portal/reportDocument.js'

for (const heading of ['参考文献', 'References', 'references', '2. 参考资料']) {
  test(`saving authored ${heading} does not append duplicate references`, () => {
    const output = buildReportMarkdown({ title: '报告', sections: [
      { title: '分析', content: '事实[1]。' }, { title: heading, content: '[1] 原始来源' },
    ], citations: [{ id: 1, title: '原始来源' }] })
    assert.equal((output.match(/^## (?:参考资料|参考文献|references)$/gim) || []).length, 1)
    assert.equal((output.match(/\[1\] 原始来源/g) || []).length, 1)
  })
}

// Model the heading/body boundary used by the backend Markdown reader.
function reload(content) {
  return content.split(/^## /m).slice(1).map((chunk, index) => {
    const [title, ...body] = chunk.split('\n')
    return { id: index + 1, title, content: body.join('\n').trim() }
  })
}

test('grouped citations stay mapped after repeated saves without evidence-note parentheses', () => {
  const citations = [{ id: 1, sourceId: '26' }, { id: 2, sourceId: '18' }, { id: 3, sourceId: '19' }]
  const first = buildReportMarkdown({ title: '报告', citations, sections: [
    { title: '正文', content: '依据[资料18；资料19，新闻正文]及[资料26]，未知[资料99]。' },
  ] })
  assert.match(first, /依据，未知\[资料99\]\[2\]\[3\]\[1\]。/)
  assert.equal(buildReportMarkdown({ title: '报告', citations, sections: reload(first) }), first)
})

test('save/reload is stable with six chapters, preparation notes and authored references', () => {
  const sections = Array.from({ length: 6 }, (_, i) => ({ title: `${i + 1}. 章节${i + 1}`, content: `正文${i + 1}\n\n- 依据[资料18]\n- 保留条目` }))
  sections.push({ title: '编制说明', content: '边界与方法。' }, { title: '参考资料', content: '[资料18] 原始文献与说明。' })
  const snapshot = structuredClone(sections)
  const citations = [{ id: 1, sourceId: '18', title: '原始文献', source: { name: '来源甲' } }]
  const first = buildReportMarkdown({ title: '科研报告', sections, citations })
  assert.equal((first.match(/^## 参考资料$/gm) || []).length, 1)
  assert.equal(reload(first).length, 8)
  assert.ok(first.includes(sections[0].content.replace('[资料18]', '[1]')))
  assert.ok(first.includes('[1] 原始文献与说明。'))
  let saved = first
  for (let i = 0; i < 3; i++) saved = buildReportMarkdown({ title: '科研报告', sections: reload(saved), citations })
  assert.equal(saved, first)
  assert.deepEqual(sections, snapshot)
  assert.doesNotMatch(first, /^## \d+\./m)
})

test('references use consecutive ordinals and human-readable source objects', () => {
  const content = buildReportMarkdown({ title: '报告', sections: [{ title: '结论', content: '根据[资料18]及[资料9007199254740993]。' }], citations: [
    { id: 1, sourceId: '18', title: '新闻', source: { name: '管网发布', url: 'https://example.org/news' } },
    { id: 2, sourceId: '9007199254740993', title: '论文', source: { journal: '研究期刊', doi: '10.1/example' } },
    { id: 3, sourceId: '20', title: '文件', source: { filename: '研究资料.pdf' } },
    { id: 4, sourceId: '21', title: '旧来源', source: '来源名称' },
  ] })
  assert.match(content, /\[1\] 新闻（管网发布/)
  assert.match(content, /\[2\] 论文（研究期刊/)
  assert.match(content, /根据\[1\]\[2\]。/)
  assert.match(content, /研究资料\.pdf/)
  assert.match(content, /来源名称/)
  assert.doesNotMatch(content, /\[object Object\]|undefined/)
  assert.equal(buildReportMarkdown({ title: '报告', sections: reload(content), citations: [] }), content)
})

test('empty reference section is filled once; absent citations do not fabricate references', () => {
  const citations = [{ id: 7, title: '标题', source: {} }]
  const content = buildReportMarkdown({ title: '报告', sections: [{ title: '参考资料', content: '' }], citations })
  assert.match(content, /\[1\] 标题/)
  assert.equal((content.match(/^## 参考资料$/gm) || []).length, 1)
  assert.equal(buildReportMarkdown({ title: '报告', sections: [], citations: [] }).trim(), '# 报告')
})

test('editor load/save/reload uses the serializer and never auto-loads retired publications', async () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const scope = effectScope(), errors = [], payloads = []
  let publicationCalls = 0
  let stored = { id: '33', title: '报告', type: 'research', versionNo: 1, revision: 1,
    sections: [{ id: 1, title: '1. 结论', content: '保留正文[资料18]。', citationIds: [1] }, { id: 2, title: '参考资料', content: '[资料18] 证据。' }],
    citations: [{ id: 1, sourceId: '18', title: '证据', source: { url: 'https://example.org' } }] }
  const context = vm.createContext({
    ref, computed, watch, buildReportMarkdown, cleanReportCitationNotes, onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    useRoute: () => ({ params: { id: '33' } }), useRouter: () => ({}), usePortalStore: () => ({ researchReports: [] }),
    getPipelineResearchReport: async () => ({ data: structuredClone(stored) }),
    listPipelineResearchReportVersions: async () => ({ data: { rows: [] } }),
    listPipelineResearchReportExports: async () => ({ data: { rows: [] } }),
    listPipelineResearchReportPublications: async () => { publicationCalls++; throw new Error('NotFound') },
    updatePipelineResearchReport: async (_id, payload) => {
      payloads.push(payload)
      stored = { ...stored, ...JSON.parse(JSON.stringify(payload)), sections: reload(payload.content), revision: stored.revision + 1 }
      return { data: structuredClone(stored) }
    },
    ElMessage: { error(message) { errors.push(message) }, warning() {}, success() {} },
    setTimeout() { return 1 }, clearTimeout() {},
  })
  try {
    scope.run(() => vm.runInContext(`${source}\nglobalThis.editor = { loadReport, markSaving, saveCurrent, buildMarkdown, reportTypeLabel, sections, citations }`, context))
    const view = context.editor
    await view.loadReport()
    assert.equal(view.reportTypeLabel.value, '科研报告')
    const expected = view.buildMarkdown()
    for (let i = 0; i < 3; i++) {
      view.markSaving()
      assert.equal(await view.saveCurrent(), true)
      await view.loadReport()
      assert.equal(view.buildMarkdown(), expected)
    }
    assert.equal(payloads.length, 3)
    assert.equal(payloads[0].sections[0].content, '保留正文[资料18]。')
    assert.equal(view.citations.value[0].sourceId, '18')
    assert.equal(publicationCalls, 0)
    assert.deepEqual(errors, [])
  } finally { scope.stop() }
})
