import { decimalId } from './businessId.js'

export const LEGACY_DETAIL_NOTICE = '编号已更新，请从列表重新打开。'

const detailPaths = [
  [/^\/portal\/news\/([^/]+)\/?$/, '/portal/news'],
  [/^\/portal\/papers\/([^/]+)\/?$/, '/portal/papers'],
  [/^\/portal\/knowledge\/([^/]+)\/?$/, '/portal/knowledge'],
  [/^\/portal\/research\/tasks\/([^/]+)\/?$/, '/portal/research'],
  [/^\/portal\/research\/reports\/([^/]+)(?:\/diagram)?\/?$/, '/portal/research'],
  [/^\/portal\/digests\/([^/]+)\/?$/, '/portal/digests']
]

// Runs before the detail component is resolved, so old bookmarks cannot fetch
// a UUID from the numeric API. Creation forms and their query/text stay intact.
export function legacyDetailGuard(notify) {
  return to => {
    for (const [pattern, list] of detailPaths) {
      const match = to.path.match(pattern)
      if (!match || (list === '/portal/digests' && match[1] === 'create')) continue
      let id
      try { id = decodeURIComponent(match[1]) } catch { id = '' }
      if (decimalId(id)) return
      notify(LEGACY_DETAIL_NOTICE)
      return { path: list, replace: true }
    }
  }
}
