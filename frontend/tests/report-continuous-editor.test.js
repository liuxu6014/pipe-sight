import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref, watch, effectScope } from 'vue'

function setup(globals = {}) {
  const text = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
  const source = text.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const scope = effectScope()
  const context = vm.createContext({ ref, computed, watch, onMounted() {}, onBeforeUnmount() {},
    onBeforeRouteLeave() {}, onBeforeRouteUpdate() {}, useRoute: () => ({ params: { id: '33' }, path: '/portal/research/reports/33', query: {} }),
    useRouter: () => ({}), usePortalStore: () => ({ researchReports: [], digestReports: [] }), setTimeout() {}, clearTimeout() {}, ...globals,
  })
  scope.run(() => vm.runInContext(`${source}\nglobalThis.editor = { sections, currentSectionId, updateSectionContent, updateSectionTitle, setSectionElement, setSectionBody, applyFormat, scrollToSection, syncVisibleSection, documentScrollRef, outlinePanelRef, keepActiveOutlineVisible }`, context))
  return { text, editor: context.editor, close: () => scope.stop() }
}

test('the article renders all sections and editing a non-active chapter never overwrites another chapter', () => {
  const view = setup()
  try {
    assert.match(view.text, /<section v-for="\(section, index\) in sections"/)
    const { editor } = view
    editor.sections.value = [{ id: 1, title: '首章', content: '第一章原文' }, { id: 2, title: '末章', content: '第二章原文' }]
    editor.updateSectionContent({ currentTarget: { innerText: '第二章修改后的正文' } }, editor.sections.value[1])
    assert.equal(editor.sections.value[0].content, '第一章原文')
    assert.equal(editor.sections.value[1].content, '第二章修改后的正文')
    editor.updateSectionTitle({ currentTarget: { innerText: '末章新标题' } }, editor.sections.value[1])
    assert.equal(editor.sections.value[0].title, '首章')
    assert.equal(editor.sections.value[1].title, '末章新标题')
  } finally { view.close() }
})

test('outline navigation scrolls the existing document; scrolling updates the active outline item', () => {
  const view = setup()
  try {
    const { editor } = view
    let target
    editor.sections.value = [{ id: 1 }, { id: 2 }]
    editor.documentScrollRef.value = { getBoundingClientRect: () => ({ top: 0 }) }
    editor.setSectionElement(1, { getBoundingClientRect: () => ({ top: -500 }), scrollIntoView() {} })
    editor.setSectionElement(2, { getBoundingClientRect: () => ({ top: 40 }), scrollIntoView(options) { target = options } })
    editor.scrollToSection(2)
    assert.equal(editor.currentSectionId.value, 2)
    assert.equal(target.block, 'start')
    editor.currentSectionId.value = 1
    editor.syncVisibleSection()
    assert.equal(editor.currentSectionId.value, 2)
    editor.setSectionElement(2, { getBoundingClientRect: () => ({ top: 500 }) })
    Object.assign(editor.documentScrollRef.value, { scrollTop: 900, clientHeight: 100, scrollHeight: 1000 })
    editor.currentSectionId.value = 1
    editor.syncVisibleSection()
    assert.equal(editor.currentSectionId.value, 2)
  } finally { view.close() }
})

test('active directory item stays below its sticky heading without moving the article', () => {
  const view = setup()
  try {
    const { editor } = view
    let row = { top: 360, bottom: 400 }
    editor.documentScrollRef.value = { scrollTop: 850 }
    editor.outlinePanelRef.value = {
      scrollTop: 0,
      getBoundingClientRect: () => ({ top: 100, bottom: 300 }),
      querySelector: selector => selector === '[aria-current="location"]'
        ? { getBoundingClientRect: () => row }
        : { getBoundingClientRect: () => ({ height: 48 }) }
    }
    editor.keepActiveOutlineVisible()
    assert.equal(editor.outlinePanelRef.value.scrollTop, 108)
    row = { top: 120, bottom: 160 }
    editor.keepActiveOutlineVisible()
    assert.equal(editor.outlinePanelRef.value.scrollTop, 72)
    row = { top: 180, bottom: 220 }
    editor.keepActiveOutlineVisible()
    assert.equal(editor.outlinePanelRef.value.scrollTop, 72)
    assert.equal(editor.documentScrollRef.value.scrollTop, 850)
  } finally { view.close() }
})

test('formatting a selected passage uses its owning chapter even after scroll activates a different chapter', () => {
  const view = setup({ window: { getSelection: () => ({ toString: () => '选中文字', rangeCount: 1, anchorNode: 'first-body' }) },
    document: { execCommand: () => true } })
  try {
    const { editor } = view
    editor.sections.value = [{ id: 1, title: '第一章', content: '原文一' }, { id: 2, title: '第二章', content: '原文二' }]
    editor.setSectionBody(1, { contains: node => node === 'first-body', innerText: '**选中文字**' })
    editor.setSectionBody(2, { contains: () => false, innerText: '原文二' })
    editor.currentSectionId.value = 2
    editor.applyFormat('B')
    assert.equal(editor.sections.value[0].content, '**选中文字**')
    assert.equal(editor.sections.value[1].content, '原文二')
  } finally { view.close() }
})
