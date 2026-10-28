<template>
  <aside id="portal-desktop-nav" class="ps-desktop-sidebar" :class="{ 'is-collapsed': collapsed }">
    <nav aria-label="用户端左侧导航">
      <a v-for="(item, index) in portalNavigation" :key="item.path" :href="item.path" :class="{ 'is-active': item.match(route.path) }" :aria-current="item.match(route.path) ? 'page' : undefined" :aria-label="item.label" :title="collapsed ? item.label : undefined" @click="navigate($event, item.path)">
        <component :is="icons[index]" aria-hidden="true" /><span v-if="!collapsed">{{ item.label }}</span>
      </a>
      <a class="ps-sidebar-basket" href="/portal/basket" :class="{ 'is-active': isBasketPath(route.path) }" :aria-current="isBasketPath(route.path) ? 'page' : undefined" :aria-label="`资料库，${store.libraryCount} 条资料`" :title="collapsed ? `资料库（${store.libraryCount}）` : undefined" @click="navigate($event, '/portal/basket')"><Collection aria-hidden="true" /><span v-if="!collapsed">资料库</span><b v-if="store.libraryCount" class="ps-sidebar-basket-count" aria-hidden="true">{{ store.libraryCount > 99 ? '99+' : store.libraryCount }}</b></a>
    </nav>
    <button class="ps-sidebar-toggle" type="button" :aria-label="collapsed ? '展开左侧导航' : '收起左侧导航'" :aria-expanded="!collapsed" aria-controls="portal-desktop-nav" @click="layout.toggle()"><Expand v-if="collapsed" /><Fold v-else /><span v-if="!collapsed">收起导航</span></button>
  </aside>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { House, Reading, Document, EditPen, Notebook, Expand, Fold, Collection } from '@element-plus/icons-vue'
import { portalNavigation, isBasketPath } from '../data'
import usePortalStore from '@/store/modules/portal'

const route = useRoute(), router = useRouter()
const store = usePortalStore()
const layout = inject('portalNavigationLayout')
const collapsed = computed(() => layout.collapsed.value)
const icons = [House, Reading, Document, EditPen, Notebook]
function navigate(event, path) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  router.push(path)
}
</script>

<style scoped>
.ps-desktop-sidebar { display: none; }
@media (min-width: 1051px) {
  .ps-desktop-sidebar { position: fixed; top: 70px; bottom: 0; left: 0; z-index: 90; display: flex; flex-direction: column; width: var(--ps-navigation-width); padding: 12px 8px; border-right: 1px solid var(--ps-line); background: #fff; }
  nav { display: grid; align-content: start; gap: 4px; flex: 1; overflow-y: auto; }
  nav a, .ps-sidebar-toggle { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 12px; border: 0; border-radius: 6px; background: transparent; color: var(--ps-ink-2); font: inherit; font-size: 14px; text-decoration: none; cursor: pointer; white-space: nowrap; }
  nav a:hover, .ps-sidebar-toggle:hover { background: #f5f8fb; }
  nav a.is-active { background: var(--ps-blue-soft); color: var(--ps-blue); font-weight: 600; }
  svg { width: 18px; height: 18px; flex: 0 0 18px; }
  .ps-sidebar-toggle { margin-top: 12px; color: var(--ps-muted); }
  .is-collapsed nav a, .is-collapsed .ps-sidebar-toggle { justify-content: center; padding: 0; }
  .ps-sidebar-basket { position: relative; margin-top: 8px; }
  .ps-sidebar-basket-count { display: grid; place-items: center; min-width: 20px; height: 20px; padding: 0 5px; margin-left: auto; border-radius: 10px; background: var(--ps-blue-soft); color: var(--ps-blue); font-size: 11px; font-weight: 600; }
  .is-collapsed .ps-sidebar-basket-count { position: absolute; top: 0; right: 0; height: 16px; min-width: 16px; padding: 0 3px; border: 1px solid #fff; font-size: 10px; }
}
</style>
