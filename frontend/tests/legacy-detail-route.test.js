import test from 'node:test'
import assert from 'node:assert/strict'
import { createRouter, createMemoryHistory } from 'vue-router'
import { readFileSync } from 'node:fs'
import { legacyDetailGuard, LEGACY_DETAIL_NOTICE } from '../src/utils/portal/legacyRoute.js'

test('old browser detail bookmarks return to their list before a detail can resolve or request data', async () => {
  const pairs = [
    ['/portal/papers/curated-paper-550e8400-e29b-41d4-a716-446655440000', '/portal/papers'],
    ['/portal/news/old-article-uuid', '/portal/news'],
    ['/portal/knowledge/old-file-uuid', '/portal/knowledge'],
    ['/portal/research/tasks/old-task-uuid', '/portal/research'],
    ['/portal/research/reports/old-report-uuid', '/portal/research'],
    ['/portal/research/reports/old-report-uuid/diagram', '/portal/research'],
    ['/portal/digests/old-digest-uuid', '/portal/digests']
  ]
  const messages = [], requests = []
  const router = createRouter({ history: createMemoryHistory(), routes: pairs.flatMap(([path, list], index) => [
    { path, name: `detail-${index}`, component: {} },
    { path: list, component: {} }
  ]) })
  router.beforeEach(legacyDetailGuard(message => messages.push(message)))
  router.beforeResolve(to => { if (to.name?.startsWith('detail-')) requests.push(to.path) })
  for (const [path, list] of pairs) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, list)
  }
  assert.deepEqual(requests, [])
  assert.equal(messages.length, pairs.length)
  assert.ok(messages.every(message => message === LEGACY_DETAIL_NOTICE))
  assert.match(readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8'), /router\.beforeEach\(legacyDetailGuard/)
})

test('large decimal detail IDs and creation forms with legacy template queries are never redirected', () => {
  const guard = legacyDetailGuard(() => assert.fail('must not redirect or discard a form'))
  for (const path of ['/portal/papers/9007199254740993', '/portal/research/reports/9223372036854775807/diagram', '/portal/research/create', '/portal/digests/create']) {
    assert.equal(guard({ path, query: { template: 'template-01' } }), undefined)
  }
  const redirect = legacyDetailGuard(() => {})({ path: '/portal/papers/9223372036854775808' })
  assert.equal(redirect.path, '/portal/papers')
})
