<template>
  <header class="ps-header">
    <div class="ps-header-inner">
      <el-button :auto-insert-space="false" class="ps-brand ps-ui-control" native-type="button" aria-label="返回首页" @click="router.push('/portal')">
        <span>
          <strong>科技情报与科研辅助平台</strong>
        </span>
      </el-button>

      <nav class="ps-main-nav" aria-label="用户端主导航">
        <el-button :auto-insert-space="false" class="ps-ui-control"
          v-for="item in portalNavigation"
          :key="item.path"
          native-type="button"
          :class="{ 'is-active': item.match(route.path) }"
          :aria-current="item.match(route.path) ? 'page' : undefined"
          @click="router.push(item.path)"
        >
          {{ item.label }}
        </el-button>
      </nav>

      <div class="ps-header-tools">
        <el-badge type="primary" :value="store.runningTaskCount" :hidden="!store.runningTaskCount" :max="99" class="ps-generation-queue-badge">
          <el-button :icon="Clock" class="ps-generation-queue ps-ui-control" aria-label="生成队列" title="生成队列" aria-haspopup="dialog" @click="store.taskPanelVisible = true"><span class="ps-generation-queue-label">生成队列</span></el-button>
        </el-badge>
        <el-button
          class="ps-header-search ps-ui-control"
          :icon="Search"
          aria-label="搜索平台内容"
          aria-haspopup="dialog"
          @click="openSearch"
        >搜索资讯、论文、资料</el-button>

        <el-button :auto-insert-space="false"
          v-if="store.dataError || store.dataLoading"
          class="ps-sync-status ps-ui-control"
          :class="{ 'is-loading': store.dataLoading }"
          native-type="button"
          aria-live="polite"
          :title="store.dataLoading ? '正在同步实时数据' : store.dataError"
          :aria-label="store.dataLoading ? '正在同步实时数据' : `${store.dataError}，点击重试`"
          @click="store.hydrate(true)"
        >
          <i class="ps-sync-status-dot" aria-hidden="true"></i>
          <Refresh :class="{ 'is-loading': store.dataLoading }" />
          <span>{{ store.dataLoading ? '正在同步' : '数据同步异常' }}</span>
        </el-button>

        <el-button :icon="Collection" :auto-insert-space="false"
          class="ps-basket-button ps-ui-control"
          native-type="button"
          :aria-label="`资料库，${store.libraryCount} 条资料`"
          @click="router.push('/portal/basket')"
        >

          <span>资料库</span>
          <b>{{ store.libraryCount > 99 ? '99+' : store.libraryCount }}</b>
        </el-button>

        <div class="ps-user-account-actions">
          <el-dropdown trigger="click" @command="handleCommand">
            <el-button :auto-insert-space="false" class="ps-user-button ps-ui-control" native-type="button" :aria-label="`${currentUserName}，账户菜单`">
              <PortalUserAvatar />
              <span class="ps-user-name">{{ currentUserName }}</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu class="ps-user-menu">
                <el-dropdown-item command="profile"><User />个人资料</el-dropdown-item>
                <el-dropdown-item v-if="isAdministrator" divided command="management"><Setting />管理控制台</el-dropdown-item>
                <el-dropdown-item divided command="logout"><SwitchButton />退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-button :icon="Menu" circle :auto-insert-space="false"
          class="ps-mobile-menu ps-ui-control"
          native-type="button"
          :aria-label="mobileOpen ? '收起导航' : '打开导航'"
          :aria-expanded="mobileOpen"
          aria-controls="portal-mobile-nav"
          @click="mobileOpen = !mobileOpen"
         />
      </div>
    </div>

    <nav v-if="mobileOpen" id="portal-mobile-nav" class="ps-mobile-nav" aria-label="移动端主导航" @keydown.esc="mobileOpen = false">
      <el-button
        class="ps-mobile-search ps-ui-control"
        :icon="Search"
        aria-label="搜索平台内容（移动端）"
        aria-haspopup="dialog"
        @click="openSearch"
      >搜索资讯、论文、资料</el-button>
      <el-button :auto-insert-space="false" class="ps-ui-control"
        v-for="item in portalNavigation"
        :key="item.path"
        native-type="button"
        :class="{ 'is-active': item.match(route.path) }"
        :aria-current="item.match(route.path) ? 'page' : undefined"
        @click="goMobile(item.path)"
      >
        {{ item.label }}
      </el-button>
    </nav>

    <el-dialog
      :model-value="searchOpen"
      :before-close="closeSearch"
      class="ps-global-search-dialog"
      width="min(820px, calc(100vw - 24px))"
      align-center
      center
      append-to-body
      destroy-on-close
      @opened="dialogSearch?.focusSearch()"
    >
      <template #header="{ titleId, titleClass }">
        <div class="ps-global-search-heading">
          <h2 :id="titleId" :class="titleClass">全局搜索</h2>
          <span class="ps-global-search-status" role="status">{{ dialogSearch?.dialogStatus }}</span>
        </div>
      </template>
      <SearchView ref="dialogSearch" in-dialog :initial-filters="searchFilters" @filters-changed="rememberSearch" @result-opened="closeSearch" />
    </el-dialog>
  </header>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Collection, Menu, Refresh, Search, Setting, SwitchButton, User } from '@element-plus/icons-vue'
import { portalNavigation } from '../data'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'
import PortalUserAvatar from './PortalUserAvatar.vue'
import SearchView from '../pages/SearchView.vue'
import { isManagementIdentity } from '@/utils/portal/auth'

const route = useRoute()
const router = useRouter()
const store = usePortalStore()
const userStore = useUserStore()
const searchOpen = ref(false)
const dialogSearch = ref(null)
const mobileOpen = ref(false)
watch(() => route.fullPath, () => { mobileOpen.value = false })
const searchFilters = ref({})
const history = router.options.history
function openSearch() {
  return router.push({
    path: route.path, query: route.query, hash: route.hash, force: true,
    state: { wizard: history.state.wizard, portalSearch: { owner: userStore.id } }
  })
}
function closeSearch() {
  if (history.state.portalSearch?.owner === userStore.id && searchOpen.value) router.back()
}
function rememberSearch(filters) {
  if (!searchOpen.value || history.state.portalSearch?.owner !== userStore.id) return
  history.replace(route.fullPath, { ...history.state, portalSearch: { owner: userStore.id, filters } })
}
watch([() => router.currentRoute.value, () => userStore.id], () => {
  const entry = history.state.portalSearch
  searchOpen.value = Boolean(entry && entry.owner === userStore.id)
  if (searchOpen.value) searchFilters.value = entry.filters || {}
}, { immediate: true })
const currentUserName = computed(() => userStore.nickName || userStore.name || '用户')
const isAdministrator = computed(() => isManagementIdentity(userStore.roles, userStore.permissions))

function handleCommand(command) {
  if (command === 'profile') {
    router.push('/portal/profile')
    return
  }
  if (command === 'management' && isAdministrator.value) {
    router.push('/pipeline/dashboard')
    return
  }
  if (command === 'logout') {
    userStore.logOut().finally(() => router.replace('/login'))
    return
  }
}

function goMobile(path) {
  mobileOpen.value = false
  router.push(path)
}

onMounted(() => store.hydrate())
</script>

<style scoped>
@media (min-width: 1051px) {
  .ps-main-nav, .ps-basket-button { display: none; }
}
.ps-generation-queue-badge { flex-shrink: 0; }
.ps-generation-queue { margin: 0; }
.ps-user-account-actions { display: flex; align-items: center; }
.ps-header-search.el-button, .ps-mobile-search.el-button {
  justify-content: flex-start;
  column-gap: 6px;
  background: #f6f8fb;
  color: var(--ps-muted);
}
.ps-header-search.el-button:hover, .ps-mobile-search.el-button:hover { color: var(--ps-blue); }
.ps-mobile-search.el-button { grid-column: 1 / -1; min-width: 0; }
:global(.ps-global-search-dialog.el-dialog.is-align-center) {
  --el-dialog-padding-primary: clamp(12px, 2.5vw, 20px);
  --el-dialog-border-radius: 12px;
  margin-top: auto !important; /* Override the legacy dialog top offset. */
}
:global(.ps-global-search-dialog .el-dialog__header.show-close) {
  padding-inline: calc(var(--el-dialog-padding-primary) + var(--el-message-close-size, 16px));
}
.ps-global-search-heading { display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline; }
.ps-global-search-heading h2 { margin: 0; font-weight: 500; }
.ps-global-search-status { color: var(--ps-muted); font-size: 14px; }
.ps-global-search-status:not(:empty) { margin-inline-start: 10px; }
@media (min-width: 1051px) and (max-width: 1280px) {
  .ps-header-search.el-button { display: inline-flex; }
}
@media (max-width: 1050px) {
  .ps-header-search.el-button { display: none; }
  .ps-header-tools .ps-generation-queue.el-button { min-height: 44px; }
}
@media (max-width: 760px) {
  .ps-header-tools { flex: 0 0 auto; gap: 4px; }
  .ps-header-tools > * { flex-shrink: 0; }
  .ps-header-tools .el-button:is(.ps-generation-queue, .ps-basket-button, .ps-user-button, .ps-mobile-menu, .ps-sync-status) {
    flex: 0 0 44px;
    width: 44px;
    min-width: 44px;
    height: 44px;
    min-height: 44px;
    padding: 0;
  }
  .ps-generation-queue-label { display: none; }
  .ps-header-tools .ps-basket-button { position: relative; }
  .ps-header-tools .ps-basket-button b {
    position: absolute;
    top: 1px;
    right: 0;
    min-width: 17px;
    height: 17px;
    padding-inline: 3px;
    line-height: 1;
  }
}
</style>
