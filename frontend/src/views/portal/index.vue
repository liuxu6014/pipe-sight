<template>
  <div class="ps-portal pipeline-user-portal portal-app-shell" :data-page="portalPage">
    <PortalHeader />
    <main class="ps-portal-main">
      <router-view v-slot="{ Component }">
        <transition name="ps-page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <footer class="ps-footer">
      <span>国家管网科技情报与科研辅助平台</span>
      <span>数据仅按当前账号授权范围展示</span>
    </footer>
    <PortalTaskPanel />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PortalHeader from './components/PortalHeader.vue'
import PortalTaskPanel from './components/PortalTaskPanel.vue'

defineOptions({ name: 'PipelineUserPortal' })

const route = useRoute()
const portalPage = computed(() => route.name || 'PortalHome')
</script>
