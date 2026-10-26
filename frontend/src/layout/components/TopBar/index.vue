<template>
  <el-menu class="topbar-menu" :ellipsis="false" :default-active="activeMenu" :active-text-color="theme" mode="horizontal">
    <sidebar-item :key="route.path + index" v-for="(route, index) in topMenus" :item="route" :base-path="route.path" />

    <el-sub-menu index="more" class="el-sub-menu__hide-arrow" v-if="moreRoutes.length > 0">
      <template #title>
        <span>更多菜单</span>
      </template>
      <sidebar-item :key="route.path + index" v-for="(route, index) in moreRoutes" :item="route" :base-path="route.path" />
    </el-sub-menu>
  </el-menu>
</template>

<script setup>
import SidebarItem from '../Sidebar/SidebarItem'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'
import { resolveActiveNavigation, splitNavigationMenus } from '@/utils/management-navigation'

const route = useRoute()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()

const theme = computed(() => settingsStore.theme)
const activeMenu = computed(() => resolveActiveNavigation(route, permissionStore.navigationRoutes))

const visibleNumber = ref(5)
const menuPartition = computed(() => splitNavigationMenus(permissionStore.navigationRoutes, visibleNumber.value))
const topMenus = computed(() => menuPartition.value.visible)
const moreRoutes = computed(() => menuPartition.value.more)
function setVisibleNumber() {
  const width = document.body.getBoundingClientRect().width / 3
  visibleNumber.value = Math.max(1, Math.floor(width / 85))
}

onMounted(() => {
  window.addEventListener('resize', setVisibleNumber)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', setVisibleNumber)
})

onMounted(() => {
  setVisibleNumber()
})
</script>

<style lang="scss">
/* menu item */
.topbar-menu.el-menu--horizontal .el-submenu__title, .topbar-menu.el-menu--horizontal .el-menu-item {
  padding: 0 10px !important;
}

.topbar-menu.el-menu--horizontal > .el-menu-item {
  float: left;
  height: 50px !important;
  line-height: 50px !important;
  color: #303133 !important;
  padding: 0 5px !important;
  margin: 0 10px !important;
}

.el-sub-menu.is-active .svg-icon, .el-menu-item.is-active .svg-icon + span, .el-sub-menu.is-active .svg-icon + span, .el-sub-menu.is-active .el-sub-menu__title span {
  color: v-bind(theme);
}

/* sub-menu item */
.topbar-menu.el-menu--horizontal > .el-sub-menu .el-sub-menu__title {
  float: left;
  line-height: 50px !important;
  color: #303133 !important;
  margin: 0 15px -3px!important;
}

/* topbar more arrow */
.topbar-menu .el-sub-menu .el-sub-menu__icon-arrow {
  position: static;
  margin-left: 8px;
  margin-top: 0px;
  display: block !important;
}

/* menu__title el-menu-item */
.topbar-menu.el-menu--horizontal .el-sub-menu__title, .topbar-menu.el-menu--horizontal .el-menu-item {
  height: 60px;
}
</style>
