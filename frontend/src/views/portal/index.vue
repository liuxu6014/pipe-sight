<template>
  <div class="ps-portal pipeline-user-portal portal-app-shell" :class="{ 'is-nav-collapsed': navigationCollapsed }" :data-page="portalPage">
    <a class="ps-skip-link" href="#portal-main">跳至主要内容</a>
    <PortalHeader />
    <PortalSidebar />
    <main id="portal-main" class="ps-portal-main ps-workspace-surface" tabindex="-1">
      <router-view v-slot="{ Component, route: pageRoute }">
        <transition name="ps-page" mode="out-in">
          <component :is="Component" :key="pageRoute.path" />
        </transition>
      </router-view>
    </main>
    <PortalTaskPanel />
  </div>
</template>

<script setup>
import { computed, provide, ref } from 'vue'
import { useRoute } from 'vue-router'
import PortalHeader from './components/PortalHeader.vue'
import PortalTaskPanel from './components/PortalTaskPanel.vue'
import PortalSidebar from './components/PortalSidebar.vue'

defineOptions({ name: 'PipelineUserPortal' })

const route = useRoute()
const portalPage = computed(() => route.name || 'PortalHome')
const navigationCollapsed = ref(false)
try { navigationCollapsed.value = localStorage.getItem('ps-portal-navigation-collapsed') === 'true' } catch { /* 存储不可用时仍可切换 */ }
function toggleNavigation() {
  navigationCollapsed.value = !navigationCollapsed.value
  try { localStorage.setItem('ps-portal-navigation-collapsed', String(navigationCollapsed.value)) } catch { /* 保留当前会话状态 */ }
}
provide('portalNavigationLayout', { collapsed: navigationCollapsed, toggle: toggleNavigation })
</script>

<style scoped>
@media (min-width: 1051px) {
  .portal-app-shell { --ps-navigation-width: 180px; }
  .portal-app-shell.is-nav-collapsed { --ps-navigation-width: 60px; }
  .ps-portal-main { margin-left: var(--ps-navigation-width); }
}
</style>
