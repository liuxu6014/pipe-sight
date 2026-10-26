import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { formatBusinessTime } from '../src/utils/portal/businessTime.js'
import * as businessIds from '../src/utils/portal/businessId.js'

const settled = () => new Promise(resolve => setImmediate(resolve))
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function portalStore() {
  const source = readFileSync(new URL('../src/store/modules/portal.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from [^\n]+\n/gm, '')
    .replace("import.meta.env.VITE_PORTAL_DEMO_DATA === 'true'", 'false')
    .replace(/^export function /gm, 'function ')
    .replace('export default usePortalStore', 'globalThis.store = usePortalStore')
  const requests = [], mutations = []
  const read = () => { const request = deferred(); requests.push(request); return request.promise }
  const write = () => { const request = deferred(); mutations.push(request); return request.promise }
  const context = vm.createContext({
    ...businessIds, formatBusinessTime,
    fallbackDigests: [], fallbackDocuments: [], fallbackNews: [], fallbackPapers: [], recentTasks: [], fallbackReports: [], fallbackTopics: [],
    getPipelineDashboard: read, getPipelineWorkspace: read, listPipelineIntelligence: read,
    listPipelineKnowledgeDocuments: read, listPipelineReports: read, listPipelineResearchJobs: read, listPipelineResearchReports: read,
    savePipelineWorkspaceItem: write, deletePipelineWorkspaceItem: write,
    ElMessage: { error() {} },
    defineStore: (_name, options) => {
      const store = Object.assign(options.state(), options.actions)
      for (const [name, getter] of Object.entries(options.getters)) Object.defineProperty(store, name, { get: () => getter(store) })
      return store
    }
  })
  vm.runInContext(source, context)
  return { store: context.store, requests, mutations }
}
function finishHydration(requests, name) {
  requests.forEach((request, index) => request.resolve({ data: index === 3
    ? { basket: [{ id: name }], favorites: [], favoriteItems: [] }
    : { rows: [], total: 0 } }))
}

test('portal hydration fetches unified reports once and shares report failures with digest state', async () => {
  const { store, requests } = portalStore()
  const pending = store.hydrate()
  assert.equal(requests.length, 6)
  requests.forEach((request, index) => {
    if (index === 5) request.reject(new Error('reports unavailable'))
    else request.resolve({ data: index === 3 ? { basket: [], favorites: [], favoriteItems: [] } : { rows: [], total: 0 } })
  })
  await pending
  assert.ok(store.sectionErrors.reports)
  assert.equal(store.sectionErrors.digests, store.sectionErrors.reports)
  assert.match(store.dataError, /1\/6/)
})

test('late hydration after logout cannot repopulate the cleared workspace', async () => {
  const { store, requests } = portalStore()
  const previous = store.hydrate()
  store.reset()
  finishHydration(requests, '2001')
  await previous
  assert.equal(store.basket.length, 0)
  assert.equal(store.dataLoaded, false)
})

test('previous-user hydration cannot overwrite a newer session or stop its loading indicator', async () => {
  const { store, requests } = portalStore()
  const previous = store.hydrate()
  store.reset()
  const current = store.hydrate()
  finishHydration(requests.slice(0, 6), '2001')
  await previous
  assert.equal(store.dataLoading, true)
  assert.equal(store.basket.length, 0)
  finishHydration(requests.slice(6), '2002')
  await current
  assert.equal(store.basket[0].id, '2002')
  assert.equal(store.dataLoading, false)
})

test('failed old-session basket removal cannot restore an item into the new session', async () => {
  const { store, mutations } = portalStore()
  store.basket = [{ id: '2003', title: 'Previous user document' }]
  store.removeFromBasket('2003')
  store.reset()
  mutations[0].reject(new Error('old request failed'))
  await settled()
  assert.equal(store.basket.length, 0)
  assert.equal(store.dataError, '')
})

test('a late basket-add failure cannot remove a new-session item with the same ID', async () => {
  const { store, mutations } = portalStore()
  store.addToBasket({ id: '2004', title: 'Old selection' })
  store.reset()
  store.basket = [{ id: '2004', title: 'New selection' }]
  mutations[0].reject(new Error('old request failed'))
  await settled()
  assert.equal(store.basket[0].title, 'New selection')
  assert.equal(store.dataError, '')
})

test('failed old-session bulk removal cannot repopulate a cleared basket', async () => {
  const { store, mutations } = portalStore()
  store.basket = [{ id: '2005' }]
  store.clearBasket()
  store.reset()
  mutations[0].reject(new Error('old request failed'))
  await settled()
  assert.equal(store.basket.length, 0)
})

test('failed old-session favorite removal cannot restore a private favorite', async () => {
  const { store, mutations } = portalStore()
  store.favorites = ['2005']
  store.favoriteItems = [{ id: '2005' }]
  store.toggleFavorite('2005')
  store.reset()
  mutations[0].reject(new Error('old request failed'))
  await settled()
  assert.equal(store.favorites.length, 0)
  assert.equal(store.favoriteItems.length, 0)
})

test('old cached UUIDs cannot mutate workspace and clearing never silently discards them', () => {
  const { store, mutations } = portalStore()
  const old = '550e8400-e29b-41d4-a716-446655440000'
  store.basket = [{ id: old, title: '保留原选材' }]
  store.favorites = [old]
  assert.equal(store.removeFromBasket(old), false)
  assert.equal(store.toggleFavorite(old), false)
  assert.equal(store.clearBasket(), false)
  assert.equal(store.addToBasket({ id: old }), false)
  assert.equal(mutations.length, 0)
  assert.equal(store.basket[0].title, '保留原选材')
  assert.equal(store.favorites[0], old)
})
