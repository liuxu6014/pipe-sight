<template>
  <el-menu
    :default-active="activeMenu"
    mode="horizontal"
    @select="handleSelect"
    :ellipsis="false"
  >
    <template v-for="item in topMenus" :key="item.path">
      <el-menu-item :style="{'--theme': theme}" :index="item.path">
        <svg-icon
        v-if="item.meta && item.meta.icon && item.meta.icon !== '#'"
        :icon-class="item.meta.icon"/>
        {{ item.meta.title }}
      </el-menu-item>
    </template>

    <!-- 顶部菜单超出数量折叠 -->
    <el-sub-menu :style="{'--theme': theme}" index="more" v-if="moreRoutes.length">
      <template #title>更多菜单</template>
      <template v-for="item in moreRoutes" :key="item.path">
        <el-menu-item
          :index="item.path"
          >
        <svg-icon
          v-if="item.meta && item.meta.icon && item.meta.icon !== '#'"
          :icon-class="item.meta.icon"/>
        {{ item.meta.title }}
        </el-menu-item>
      </template>
    </el-sub-menu>
  </el-menu>
</template>

<script setup>
import { isExternal } from '@/utils/validate'
import useAppStore from '@/store/modules/app'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'
import { findNavigationGroup, splitNavigationMenus } from '@/utils/management-navigation'

// 顶部栏初始数
const visibleNumber = ref(5);
// 当前激活菜单的 index
const currentIndex = ref(null);

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()
const route = useRoute();
const router = useRouter();

// 主题颜色
const theme = computed(() => settingsStore.theme);
// 所有的路由信息
const routers = computed(() => permissionStore.navigationRoutes);

// 顶部显示菜单
const menuPartition = computed(() => splitNavigationMenus(routers.value, visibleNumber.value));
const topMenus = computed(() => menuPartition.value.visible);
const moreRoutes = computed(() => menuPartition.value.more);
const activeMenu = computed(() => currentIndex.value || findNavigationGroup(route, routers.value)?.path || '');

// 路由或授权菜单变化时选择其实际所属模块；computed 中不再改写路由和侧栏。
watch([() => route.path, () => route.meta.activeMenu, routers, () => settingsStore.navType], () => {
  if (Number(settingsStore.navType) !== 2) return
  const group = findNavigationGroup(route, routers.value)
  currentIndex.value = group?.path || ''
  if (group && permissionStore.selectNavigationGroup(group.path)) {
    appStore.toggleSideBarHide(false)
  } else {
    permissionStore.restoreSidebarRouters()
    appStore.toggleSideBarHide(Boolean(group))
  }
}, { immediate: true })

function setVisibleNumber() {
  const width = document.body.getBoundingClientRect().width / 3;
  visibleNumber.value = Math.max(1, Math.floor(width / 85));
}

function handleSelect(key) {
  const menu = routers.value.find(item => item.path === key && !item.hidden);
  if (!menu) return
  currentIndex.value = key;
  if (isExternal(key)) {
    // http(s):// 路径新窗口打开
    window.open(key, "_blank");
  } else if (permissionStore.selectNavigationGroup(key)) {
    appStore.toggleSideBarHide(false);
  } else {
    const query = typeof menu.query === 'string' ? JSON.parse(menu.query) : menu.query;
    router.push(query ? { path: key, query } : { path: key });
    appStore.toggleSideBarHide(true);
  }
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
.topmenu-container.el-menu--horizontal > .el-menu-item {
  float: left;
  height: 50px !important;
  line-height: 50px !important;
  color: #303133 !important;
  padding: 0 5px !important;
  margin: 0 10px !important;
}

.topmenu-container.el-menu--horizontal > .el-menu-item.is-active, .el-menu--horizontal > .el-sub-menu.is-active .el-submenu__title {
  border-bottom: 2px solid #{'var(--theme)'} !important;
  color: #303133;
}

/* sub-menu item */
.topmenu-container.el-menu--horizontal > .el-sub-menu .el-sub-menu__title {
  float: left;
  height: 50px !important;
  line-height: 50px !important;
  color: #303133 !important;
  padding: 0 5px !important;
  margin: 0 10px !important;
}

/* 背景色隐藏 */
.topmenu-container.el-menu--horizontal>.el-menu-item:not(.is-disabled):focus, .topmenu-container.el-menu--horizontal>.el-menu-item:not(.is-disabled):hover, .topmenu-container.el-menu--horizontal>.el-submenu .el-submenu__title:hover {
  background-color: #ffffff;
}

/* 图标右间距 */
.topmenu-container .svg-icon {
  margin-right: 4px;
}

/* topmenu more arrow */
.topmenu-container .el-sub-menu .el-sub-menu__icon-arrow {
  position: static;
  vertical-align: middle;
  margin-left: 8px;
  margin-top: 0px;
}
</style>
