import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile, computed, createRenderer, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter, RouterView, useRoute } from 'vue-router'

test('switching between resource IDs creates fresh page state without remounting for query-only changes', async () => {
  // 去掉视觉动画；实际门户模板及 RouterView 决定页面实例的生命周期。
  const template = readFileSync(new URL('../src/views/portal/index.vue', import.meta.url), 'utf8')
    .split('<template>')[1].split('</template>')[0].replace(/<\/?transition[^>]*>/g, '')
  const created = []
  const Page = { setup() { created.push(useRoute().params.id); return () => h('div', 'resource') } }
  const Empty = { render: () => null }
  const Shell = {
    components: { RouterView, PortalHeader: Empty, PortalTaskPanel: Empty, PortalSidebar: Empty },
    setup() { const route = useRoute(); return { navigationCollapsed: false, portalPage: computed(() => route.name || '') } },
    render: compile(template)
  }
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/portal', component: Shell, children: [{ path: 'resource/:id', component: Page }] }] })
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
  const app = renderer.createApp({ render: () => h(RouterView) }).use(router)
  try {
    await router.push('/portal/resource/a')
    app.mount(node('root'))
    await nextTick()
    await router.push('/portal/resource/b')
    await nextTick()
    assert.deepEqual(created, ['a', 'b'])
    await router.push('/portal/resource/b?panel=sources')
    await nextTick()
    assert.deepEqual(created, ['a', 'b'])
  } finally { app.unmount() }
})
