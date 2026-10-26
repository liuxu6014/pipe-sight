import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as businessTimes from '../src/utils/portal/businessTime.js'
import * as businessIds from '../src/utils/portal/businessId.js'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { researchEvidenceRow, selectionReferences, useEvidenceSelection } from '../src/utils/portal/evidenceInput.js'
import { resolveBasketSelection } from '../src/utils/portal/basketSelection.js'

test('a preselected template receives its published version and outline after asynchronous loading', async () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchCreateView.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const context = vm.createContext({
    ...businessIds, ...businessTimes, computed, reactive, ref, watch, nextTick, onMounted() {}, onBeforeUnmount() {},
    researchEvidenceRow, selectionReferences, useEvidenceSelection, resolveBasketSelection,
    getPipelineIntelligenceDetail: async () => ({ data: {} }),
    getPipelineKnowledgeDocument: async () => ({ data: {} }),
    useRoute: () => ({ query: { template: '9007199254740993' } }),
    useRouter: () => ({}),
    usePortalStore: () => ({ newsItems: [], paperItems: [], knowledgeDocuments: [], basket: [] }),
    listPipelineTemplates: async () => ({ data: { rows: [{
      templateKey: '9007199254740993', name: '自定义报告', version: 'V4.0',
      sections: [{ id: 1, title: '实际发布的章节', words: 1500 }]
    }] } })
  })
  const scope = effectScope()
  try {
    scope.run(() => vm.runInContext(`${source}\nglobalThis.testing = { form, outline, loadTemplates }`, context))
    await context.testing.loadTemplates()
    await nextTick()
    assert.equal(context.testing.form.version, 'V4.0')
    assert.equal(context.testing.outline.value.length, 1)
    assert.equal(context.testing.outline.value[0].title, '实际发布的章节')
  } finally {
    scope.stop()
  }
})
