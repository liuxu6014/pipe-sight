import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile, computed, createRenderer, h, nextTick, ref } from 'vue'
import { createMemoryHistory, createRouter, RouterView, useRoute, useRouter } from 'vue-router'

import { setImmediate } from 'node:timers/promises'
import { trackWizardVisit, useWizardHistory } from '../src/utils/portal/wizardHistory.js'

function portalApp(children) {
  // 去掉视觉动画；实际门户模板及 RouterView 决定页面实例的生命周期。
  const template = readFileSync(new URL('../src/views/portal/index.vue', import.meta.url), 'utf8')
    .split('<template>')[1].split('</template>')[0].replace(/<\/?transition[^>]*>/g, '')
  const Empty = { render: () => null }
  const Shell = {
    components: { RouterView, PortalHeader: Empty, PortalTaskPanel: Empty, PortalSidebar: Empty },
    setup() { const route = useRoute(); return { navigationCollapsed: false, workspaceEpoch: 0, portalPage: computed(() => route.name || '') } },
    render: compile(template)
  }
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/portal', component: Shell, children }] })
  const node = type => ({ type, children: [], parent: null })
  const renderer = createRenderer({
    createElement: node, createText: node, createComment: node,
    setText() {}, setElementText() {}, patchProp() {},
    parentNode: child => child.parent,
    nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
    insert(child, parent, anchor) {
      if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1)
      child.parent = parent
      const index = parent.children.indexOf(anchor)
      parent.children.splice(index < 0 ? parent.children.length : index, 0, child)
    },
    remove(child) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1) }
  })
  trackWizardVisit(router)
  const app = renderer.createApp({ render: () => h(RouterView) }).use(router)
  return { router, mount: () => app.mount(node('root')), close: () => app.unmount() }
}

test('switching between resource IDs creates fresh page state without remounting for query-only changes', async () => {
  const created = []
  const Page = { setup() { created.push(useRoute().params.id); return () => h('div', 'resource') } }
  const { router, mount, close } = portalApp([{ path: 'resource/:id', component: Page }])
  try {
    await router.push('/portal/resource/a')
    mount()
    await nextTick()
    await router.push('/portal/resource/b')
    await nextTick()
    assert.deepEqual(created, ['a', 'b'])
    await router.push('/portal/resource/b?panel=sources')
    await nextTick()
    assert.deepEqual(created, ['a', 'b'])
  } finally { close() }
})

test('wizard history returns to its source and keeps a revisited draft separate from a new one', async () => {
  const drafts = []
  const Wizard = { name: 'ResearchCreateView', setup() {
    const title = ref('')
    const flow = useWizardHistory(useRouter(), useRoute(), '/portal/research', () => Boolean(title.value))
    drafts.push({ title, ...flow })
    return () => h('div', title.value)
  } }
  const { router, mount, close } = portalApp([
    { path: 'research/create', component: Wizard, name: 'PortalResearchCreate' },
    { path: 'research/tasks/:id', component: { render: () => h('div') } }
  ])
  try {
    const source = '/portal/research/tasks/14'
    await router.push(source)
    mount()
    await router.push('/portal/research/create?sourceTask=14')
    await nextTick()
    const draft = drafts[0]
    draft.title.value = '项目甲'
    draft.advanceStep()
    await router.push('/portal/research/tasks/28')
    router.back()
    await setImmediate()
    assert.equal(drafts.length, 1)
    assert.equal(draft.title.value, '项目甲')
    assert.equal(draft.activeStep.value, 1)
    draft.goBack()
    await setImmediate()
    assert.equal(draft.activeStep.value, 0)
    draft.title.value = ''
    router.forward()
    await setImmediate()
    assert.equal(draft.activeStep.value, 0)
    draft.goBack()
    await setImmediate()
    assert.equal(router.currentRoute.value.fullPath, source)
    await router.push('/portal/research/create?sourceTask=14')
    await nextTick()
    assert.equal(drafts.length, 2)
    assert.equal(drafts[1].title.value, '')
  } finally { close() }
})
