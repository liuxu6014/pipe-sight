// Portal reading stays in the current tab so Back restores the originating list.
export function openPortalContent(router, path) {
  return router.push(path)
}

export function returnToPreviousPage(router, fallback, previous = router.options.history.state.back, distance = 1) {
  const path = typeof previous === 'string' ? previous.split(/[?#]/, 1)[0] : ''
  const portal = fallback.startsWith('/portal/')
  const inWorkspace = portal ? /^\/portal(?:\/|$)/.test(path) : /^\/(?:pipeline|system|monitor|tool|user|ai|index)(?:\/|$)/.test(path)
  if (inWorkspace) return distance === 1 ? router.back() : router.go(-distance)
  return router.replace(fallback)
}

export const returnFromPaperDetail = router => returnToPreviousPage(router, '/portal/papers')
export const returnFromNewsDetail = router => returnToPreviousPage(router, '/portal/news')
export const returnFromKnowledgeDetail = router => returnToPreviousPage(router, '/portal/basket')
