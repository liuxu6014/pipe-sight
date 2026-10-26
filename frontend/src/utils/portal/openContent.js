// Portal reading stays in the current tab so Back restores the originating list.
export function openPortalContent(router, path) {
  return router.push(path)
}

function returnFromContentDetail(router, fallback) {
  const previous = router.options?.history?.state?.back
  if (typeof previous === 'string' && /^\/portal(?:[/?#]|$)/.test(previous)) return router.back()
  return router.push(fallback)
}

export const returnFromPaperDetail = router => returnFromContentDetail(router, '/portal/papers')
export const returnFromNewsDetail = router => returnFromContentDetail(router, '/portal/news')
