<template>
  <aside id="portal-desktop-nav" class="ps-desktop-sidebar" :class="{ 'is-collapsed': collapsed }">
    <nav aria-label="用户端左侧导航">
      <template v-for="item in portalNavigation" :key="item.path">
        <span v-if="item.path === '/portal/news'" class="ps-sidebar-caption" aria-hidden="true">情报与科研</span>
        <a :href="item.path" :class="{ 'is-active': item.match(route.path) }" :aria-current="item.match(route.path) ? 'page' : undefined" :aria-label="item.label" :title="collapsed ? item.label : undefined" @click="navigate($event, item.path)">
          <span class="ps-sidebar-icon" aria-hidden="true">
            <component :is="navigationIcons[item.path][item.match(route.path) ? 'filled' : 'outline']" />
          </span>
          <span v-if="!collapsed">{{ item.label }}</span>
        </a>
      </template>
      <a class="ps-sidebar-basket" href="/portal/basket" :class="{ 'is-active': basketActive }" :aria-current="basketActive ? 'page' : undefined" aria-label="资料库" :title="collapsed ? '资料库' : undefined" @click="navigate($event, '/portal/basket')">
        <span class="ps-sidebar-icon" aria-hidden="true">
          <component :is="basketActive ? FolderOpenFilled : FolderOpenOutlined" />
        </span>
        <span v-if="!collapsed">资料库</span>
      </a>
    </nav>
    <div class="ps-sidebar-footer">
      <el-button :auto-insert-space="false" class="ps-sidebar-toggle ps-ui-control" native-type="button" :aria-label="collapsed ? '展开左侧导航' : '收起左侧导航'" :aria-expanded="!collapsed" aria-controls="portal-desktop-nav" @click="layout.toggle()">
        <component :is="collapsed ? MenuUnfoldOutlined : MenuFoldOutlined" class="ps-sidebar-icon" aria-hidden="true" />
        <span v-if="!collapsed">收起导航</span>
      </el-button>
    </div>
  </aside>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FolderOpenFilled, FolderOpenOutlined,
  FundFilled, FundOutlined,
  HomeFilled, HomeOutlined,
  LayoutFilled, LayoutOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined,
  ProfileFilled, ProfileOutlined,
  ReadFilled, ReadOutlined,
  SnippetsFilled, SnippetsOutlined
} from '@ant-design/icons-vue'
import { portalNavigation, isBasketPath } from '../data'

const route = useRoute(), router = useRouter()
const layout = inject('portalNavigationLayout')
const collapsed = computed(() => layout.collapsed.value)
const basketActive = computed(() => isBasketPath(route.path))
const navigationIcons = {
  '/portal': { outline: HomeOutlined, filled: HomeFilled },
  '/portal/news': { outline: ProfileOutlined, filled: ProfileFilled },
  '/portal/papers': { outline: ReadOutlined, filled: ReadFilled },
  '/portal/research': { outline: FundOutlined, filled: FundFilled },
  '/portal/digests': { outline: SnippetsOutlined, filled: SnippetsFilled },
  '/portal/templates': { outline: LayoutOutlined, filled: LayoutFilled }
}
function navigate(event, path) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  router.push(path)
}
</script>

<style scoped>
.ps-desktop-sidebar { display: none; }
@media (min-width: 1051px) {
  .ps-desktop-sidebar {
    --ps-sidebar-surface: color-mix(in srgb, var(--ps-blue) 4%, var(--ps-paper));
    --ps-sidebar-muted: color-mix(in srgb, var(--ps-blue-dark) 20%, var(--ps-muted));
    --ps-sidebar-accent: color-mix(in srgb, var(--ps-blue-dark) 73%, var(--ps-ink));
    position: fixed;
    inset: 70px auto 0 0;
    z-index: 90;
    display: flex;
    flex-direction: column;
    width: var(--ps-navigation-width);
    padding: 18px 10px 10px;
    border-right: 1px solid var(--ps-line);
    background: var(--ps-sidebar-surface);
  }
  .ps-desktop-sidebar.is-collapsed { padding-inline: 8px; }
  nav { display: grid; grid-template-columns: minmax(0, 1fr); align-content: start; gap: 3px; flex: 1; overflow-y: auto; }
  .ps-sidebar-caption { margin: 14px 12px 4px; color: var(--ps-sidebar-muted); font-size: 12px; font-weight: 600; letter-spacing: .04em; white-space: nowrap; }
  .is-collapsed .ps-sidebar-caption { margin-inline: 0; overflow: hidden; visibility: hidden; }
  nav a, .ps-sidebar-toggle { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 12px; border: 0; border-radius: 6px; background: transparent; color: var(--ps-ink-2); font: inherit; font-size: 14px; text-decoration: none; cursor: pointer; white-space: nowrap; }
  nav a { position: relative; font-weight: 500; }
  nav a:hover, .ps-sidebar-toggle:hover { background: var(--ps-blue-soft); }
  nav a.is-active {
    background: color-mix(in srgb, var(--ps-blue) 14%, var(--ps-paper));
    color: var(--ps-sidebar-accent);
    font-weight: 600;
  }
  nav a:focus-visible { outline-offset: -2px; }
  .ps-sidebar-icon {
    display: grid;
    place-items: center;
    flex: 0 0 22px;
    color: var(--ps-sidebar-muted);
    font-size: 20px;
  }
  nav a:hover .ps-sidebar-icon { color: var(--ps-sidebar-accent); }
  nav a.is-active .ps-sidebar-icon { color: inherit; }
  .ps-sidebar-footer { margin-top: 10px; padding-top: 6px; border-top: 1px solid var(--ps-line); }
  .ps-sidebar-toggle { justify-content: flex-start; width: 100%; color: var(--ps-sidebar-muted); font-size: 13px; }
  .ps-sidebar-toggle .ps-sidebar-icon { font-size: 16px; }
  .is-collapsed nav a, .is-collapsed .ps-sidebar-toggle { justify-content: center; padding: 0; }
  .ps-sidebar-basket { margin-top: 18px; }
  .ps-sidebar-basket::before {
    position: absolute;
    top: -11px;
    inset-inline: 12px;
    border-top: 1px solid var(--ps-line);
    content: '';
  }
}
</style>
