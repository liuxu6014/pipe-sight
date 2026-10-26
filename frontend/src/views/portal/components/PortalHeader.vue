<template>
  <header class="ps-header">
    <div class="ps-header-inner">
      <button class="ps-brand" type="button" aria-label="返回首页" @click="router.push('/portal')">
        <img :src="logoUrl" alt="国家管网标识" />
        <span>
          <strong>国家管网</strong>
          <small>科技情报与科研辅助平台</small>
        </span>
      </button>

      <nav class="ps-main-nav" aria-label="用户端主导航">
        <button
          v-for="item in portalNavigation"
          :key="item.path"
          type="button"
          :class="{ 'is-active': item.match(route.path) }"
          :aria-current="item.match(route.path) ? 'page' : undefined"
          @click="router.push(item.path)"
        >
          {{ item.label }}
        </button>
      </nav>

      <div class="ps-header-tools">
        <form class="ps-header-search" role="search" @submit.prevent="submitSearch">
          <Search />
          <input v-model.trim="keyword" aria-label="搜索平台内容" placeholder="搜索资讯、论文、资料" />
        </form>

        <button v-if="store.dataError" class="ps-sync-status" type="button" role="status" :title="store.dataError" :aria-label="`${store.dataError}，点击重试`" @click="store.hydrate(true)">
          <Refresh :class="{ 'is-loading': store.dataLoading }" />
          <span>数据同步异常</span>
        </button>

        <button class="ps-basket-button" type="button" :aria-label="`资料篮，${store.basketCount} 条已选资料`" @click="router.push('/portal/basket')">
          <Collection />
          <span>资料篮</span>
          <b>{{ store.basketCount }}</b>
        </button>

        <div class="ps-user-account-actions">
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="ps-user-button" type="button" :aria-label="`${currentUserName}，账户菜单`">
              <PortalUserAvatar />
              <span class="ps-user-name">{{ currentUserName }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu class="ps-user-menu">
                <el-dropdown-item command="profile"><User />个人资料</el-dropdown-item>
                <el-dropdown-item v-if="isAdministrator" divided command="management"><Setting />管理控制台</el-dropdown-item>
                <el-dropdown-item divided command="logout"><SwitchButton />退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <button class="ps-mobile-menu" type="button" :aria-label="mobileOpen ? '收起导航' : '打开导航'" :aria-expanded="mobileOpen" aria-controls="portal-mobile-nav" @click="mobileOpen = !mobileOpen"><Menu /></button>
      </div>
    </div>

    <div v-if="mobileOpen" id="portal-mobile-nav" class="ps-mobile-nav" @keydown.esc="mobileOpen = false">
      <form class="ps-mobile-search ps-search-inline" role="search" @submit.prevent="submitSearch">
        <Search /><input v-model.trim="keyword" aria-label="搜索平台内容（移动端）" placeholder="搜索资讯、论文、资料" /><button type="submit">搜索</button>
      </form>
      <button v-for="item in portalNavigation" :key="item.path" type="button" :class="{ 'is-active': item.match(route.path) }" :aria-current="item.match(route.path) ? 'page' : undefined" @click="goMobile(item.path)">{{ item.label }}</button>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Collection, Menu, Refresh, Search, Setting, SwitchButton, User } from '@element-plus/icons-vue'
import { portalNavigation } from '../data'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'
import logoUrl from '@/assets/logo/pipechina-emblem.png'
import PortalUserAvatar from './PortalUserAvatar.vue'
import { isManagementIdentity } from '@/utils/portal/auth'

const route = useRoute()
const router = useRouter()
const store = usePortalStore()
const userStore = useUserStore()
const keyword = ref('')
const mobileOpen = ref(false)
watch(() => route.fullPath, () => { mobileOpen.value = false })
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const isAdministrator = computed(() => isManagementIdentity(userStore.roles, userStore.permissions))

function submitSearch() {
  if (!keyword.value) return
  router.push({ path: '/portal/search', query: { q: keyword.value } })
}

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
.ps-user-account-actions { display: flex; align-items: center; }
</style>
