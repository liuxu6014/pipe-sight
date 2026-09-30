# 管网用户端收口整理 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将管网项目用户端整理成“一个登录入口、一个门户壳、三个一级栏目、若干详情视图”的清晰结构，并确保所有用户端内容路由都必须登录鉴权。

**Architecture:** 用户端继续接入若依 token、用户信息和权限主链路；`/portal-login` 是用户侧唯一公开入口，`/portal/**` 全部为受保护内容路由。页面结构从单个巨型 `portal/index.vue` 拆成门户壳与视图组件，产品上保持一个用户端，代码上按首页、新闻、论文、报告拆分。

**Tech Stack:** Vue 3 `<script setup>`、Vue Router、Pinia、Vite、Element Plus、Node test runner、SCSS。

---

## 当前判断

当前用户端功能能跑通，但 `frontend/src/views/portal/index.vue` 同时承载首页、新闻列表、新闻详情、论文列表、论文详情、日报周报 6 个视图。它们靠 `portalPage` 与 `data-page` 样式规则切换，不会全部同时显示，但代码组织会让人误以为“用户端有好几个系统”。

正确产品结构应为：

```text
/portal-login
  ↓ 登录成功
/portal
  ├─ 新闻资讯
  │   └─ 新闻详情
  ├─ 论文资料
  │   └─ 论文详情
  └─ 日报周报
```

用户端必须登录鉴权：

- 公开：`/portal-login`
- 受保护：`/portal`、`/portal/news/**`、`/portal/papers/**`、`/portal/reports/**`
- 后台入口 `/login` 保留给若依管理端，但用户端不展示、不跳转、不暴露入口。

## Task 1: 固化用户端鉴权规则

**Files:**

- Create: `frontend/src/utils/portal/auth.js`
- Create: `frontend/tests/pipeline-portal-auth.test.js`
- Modify: `frontend/src/permission.js`
- Modify: `frontend/tests/pipeline-intellinews-layout.test.js`

**Implementation:**

- 将 `/portal-login` 定义为 `USER_PORTAL_LOGIN_PATH`。
- `isPortalProtectedPath(path)` 只匹配 `/portal` 与 `/portal/**`。
- `isPublicAuthPath(path)` 只允许 `/login`、`/register`、`/portal-login` 免登录。
- `getLoginRedirect(fullPath)` 返回 `/portal-login?redirect=${encodeURIComponent(fullPath)}`。
- 路由守卫中无 token 访问用户端内容时统一调用 `getLoginRedirect(to.fullPath)`。

**Validation:**

```bash
cd frontend
node --test tests/pipeline-portal-auth.test.js
node --test tests/*.test.js
npm run check
```

Expected:

- `/portal/**` 均被测试标记为受保护路由。
- `/portal-login` 是用户端唯一公开入口。
- 构建成功。

## Task 2: 拆分用户端门户视图

**Files:**

- Create: `frontend/src/views/portal/components/PortalNav.vue`
- Create: `frontend/src/views/portal/components/PortalHome.vue`
- Create: `frontend/src/views/portal/components/NewsList.vue`
- Create: `frontend/src/views/portal/components/NewsDetail.vue`
- Create: `frontend/src/views/portal/components/PaperList.vue`
- Create: `frontend/src/views/portal/components/PaperDetail.vue`
- Create: `frontend/src/views/portal/components/ReportCenter.vue`
- Modify: `frontend/src/views/portal/index.vue`
- Modify: `frontend/tests/pipeline-intellinews-layout.test.js`

**Implementation:**

- `index.vue` 只保留数据加载、路由状态、公共事件和条件渲染。
- 顶部导航抽到 `PortalNav.vue`，统一控制“新闻资讯 / 论文资料 / 日报周报 / 退出”。
- 首页、新闻列表、新闻详情、论文列表、论文详情、日报周报分别拆成组件。
- 使用 `v-if / v-else-if` 条件渲染替代大量 `data-page` 隐藏规则，避免 DOM 里同时挂 6 套页面。
- 保留 IntelliNews 视觉结构：`paper-detail-view`、`research-tabs`、`analysis-tabs`、`entity-row`、`location-map`、`question-list`。

**Validation:**

```bash
cd frontend
node --test tests/pipeline-intellinews-layout.test.js
node --test tests/*.test.js
npm run check
```

Expected:

- 用户端仍只显示三类一级栏目。
- 点击新闻、论文、报告仍能进入对应页面。
- 新闻详情和论文详情仍保留 IntelliNews 参考结构。
- 用户端不出现系统管理、系统监控、系统工具、AI 管理、个人中心、后台登录。

## Task 3: 标注旧素材目录用途

**Files:**

- Create: `frontend/dayReport-web/README.md`
- Create or modify: `frontend/legacy-static/README.md`

**Implementation:**

- 标明 `dayReport-web` 是历史构建产物/视觉参考，不是当前运行页面。
- 标明当前实际用户端源码位于 `frontend/src/views/portal`。
- 不删除旧目录，避免丢失验收参考。

**Validation:**

```bash
cd frontend
rg -n "src/views/portal|dayReport-web|legacy-static" README.md dayReport-web legacy-static
```

Expected:

- 旧目录用途清楚，避免误认为存在多个用户端。

## Task 4: 最终验收

**Manual routes:**

- 未登录访问 `/portal`：跳转 `/portal-login?redirect=...`
- 未登录访问 `/portal/news/news-001`：跳转 `/portal-login?redirect=...`
- 登录后访问 `/portal`：进入用户端首页
- 点击“新闻资讯”：进入新闻列表
- 点击新闻标题：进入新闻详情
- 点击“论文资料”：进入论文列表
- 点击“查看详情”：进入论文详情
- 点击“日报周报”：进入报告中心
- 点击“退出”：回到 `/portal-login`

**Automated commands:**

```bash
cd frontend
node --test tests/*.test.js
npm run check
```

Expected:

- 所有测试通过。
- Vite 生产构建通过。

## 自审结论

该方案正确，理由如下：

1. 不破坏若依后台：后台 `/login`、动态菜单、权限、角色仍保留。
2. 用户端鉴权明确：只有 `/portal-login` 公开，所有 `/portal/**` 内容页必须登录。
3. 产品心智清楚：用户看到一个“管网项目用户端”，不是多个用户系统。
4. 代码维护性更好：大组件拆成视图组件，后续改新闻、论文、报告互不影响。
5. 风险可控：先固化鉴权，再拆组件，最后标注旧目录，不做无关重构。
