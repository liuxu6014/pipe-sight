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

        <button class="ps-icon-button ps-task-trigger" type="button" aria-label="查看任务" @click="store.openTaskPanel()">
          <Bell />
          <span v-if="store.runningTaskCount">{{ store.runningTaskCount }}</span>
        </button>

        <button class="ps-basket-button" type="button" @click="router.push('/portal/research/create')">
          <Collection />
          <span>资料篮</span>
          <b>{{ store.basketCount }}</b>
        </button>

        <el-dropdown trigger="click" @command="handleCommand">
          <button class="ps-user-button" type="button">
            <span class="ps-user-avatar">{{ userInitial }}</span>
            <span class="ps-user-name">{{ currentUserName }}</span>
            <ArrowDown />
          </button>
          <template #dropdown>
            <el-dropdown-menu class="ps-user-menu">
              <el-dropdown-item command="tasks"><List />我的任务</el-dropdown-item>
              <el-dropdown-item command="reports"><Document />我的报告</el-dropdown-item>
              <el-dropdown-item command="favorites"><Star />我的收藏</el-dropdown-item>
              <el-dropdown-item divided command="logout"><SwitchButton />退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <button class="ps-mobile-menu" type="button" aria-label="打开导航" @click="mobileOpen = !mobileOpen"><Menu /></button>
      </div>
    </div>

    <div v-if="mobileOpen" class="ps-mobile-nav">
      <button v-for="item in portalNavigation" :key="item.path" type="button" :class="{ 'is-active': item.match(route.path) }" @click="goMobile(item.path)">{{ item.label }}</button>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Bell, Collection, Document, List, Menu, Refresh, Search, Star, SwitchButton } from '@element-plus/icons-vue'
import { portalNavigation } from '../data'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'
import logoUrl from '@/assets/logo/pipechina-emblem.png'

const route = useRoute()
const router = useRouter()
const store = usePortalStore()
const userStore = useUserStore()
const keyword = ref('')
const mobileOpen = ref(false)
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const userInitial = computed(() => currentUserName.value.slice(0, 1))

function submitSearch() {
  if (!keyword.value) return
  router.push({ path: '/portal/search', query: { q: keyword.value } })
}

function handleCommand(command) {
  if (command === 'logout') {
    userStore.logOut().finally(() => router.replace('/login'))
    return
  }
  router.push(`/portal/me/${command}`)
}

function goMobile(path) {
  mobileOpen.value = false
  router.push(path)
}

onMounted(() => store.hydrate())
</script>
