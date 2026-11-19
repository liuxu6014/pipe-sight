import { computed, ref, watch } from 'vue'
import { returnToPreviousPage } from './openContent.js'

const wizardRoutes = new Set(['PortalDigestCreate', 'PortalResearchCreate'])
let visitNumber = 0
const session = Math.random().toString(36).slice(2)

// A fresh visit has its own draft. Browser Back/Forward reuses that visit,
// including when returning from a task or detail page.
export function trackWizardVisit(router) {
  const history = router.options.history
  router.afterEach((to, from, failure) => {
    if (failure || !wizardRoutes.has(to.name)) return
    let wizard = history.state.wizard
    if (!wizard || wizard.path !== to.fullPath) {
      wizard = {
        visit: session + '-' + ++visitNumber,
        path: to.fullPath,
        step: 0,
        origin: history.state.back ?? from.fullPath
      }
      history.replace(to.fullPath, { ...history.state, wizard })
    }
    to.meta.wizardVisit = wizard.visit
  })
}

export function useWizardHistory(router, route, fallback, canEnterStep) {
  const history = router.options.history
  const visit = history.state.wizard?.visit
  const firstDepth = history.state.wizard?.step || 0
  const activeStep = ref(0)
  const isCurrentVisit = () => route.meta?.wizardVisit === visit

  function advanceStep() {
    const next = activeStep.value + 1
    if (!canEnterStep(next)) return
    // Only the step changes. Keep the URL and the current component's form.
    history.push(route.fullPath, { wizard: { ...history.state.wizard, step: firstDepth + next } })
    activeStep.value = next
  }

  watch(() => router.currentRoute.value, () => {
    if (!isCurrentVisit()) return
    const next = Math.max(0, (history.state.wizard?.step || 0) - firstDepth)
    if (next > activeStep.value && !canEnterStep(next)) {
      router.go(activeStep.value - next)
      return
    }
    activeStep.value = next
  })

  function goBack() {
    if (activeStep.value > 0) return router.back()
    // After a full reload the previous in-memory draft may no longer exist.
    // Skip its old steps when leaving the fresh configuration form.
    const depth = history.state.wizard?.step || 0
    return returnToPreviousPage(router, fallback, history.state.wizard?.origin, depth + 1)
  }
  const draftQuery = computed(previous => isCurrentVisit() ? route.query : previous || {})
  return { activeStep, advanceStep, goBack, isCurrentVisit, draftQuery }
}
