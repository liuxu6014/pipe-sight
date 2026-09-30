# 管网科技情报门户界面 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将若依中的管网情报模块统一为与 `frontend/dayReport-web` 一致的科技情报门户视觉，同时保留现有登录、菜单、权限和业务接口。

**Architecture:** 以 `dayReport-web` 已构建页面的白色报刊式抬头、深蓝信息层级、1160px 阅读版心和细分隔线为视觉依据。全局管网样式集中到一个 SCSS 文件；工作台和日报周报页面采用专属布局，其余业务页通过共享的页面标题、卡片、表格和响应式规则获得一致体验。

**Tech Stack:** Vue 3 `<script setup>`、Vite、Element Plus、SCSS、Node 内置测试运行器。

---

### Task 1: 报告展示数据的可测试辅助逻辑

**Files:**
- Create: `frontend/tests/pipeline-report-presentation.test.js`
- Create: `frontend/src/utils/pipeline/reportPresentation.js`

**Step 1: Write the failing test**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { formatReportDate, getReportStatusMeta } from '../src/utils/pipeline/reportPresentation.js'

test('formats a report date for the editorial masthead', () => {
  assert.equal(formatReportDate('2026-07-13'), '2026年07月13日')
})

test('maps a reviewing report to its readable status', () => {
  assert.deepEqual(getReportStatusMeta('reviewing'), { label: '审核中', type: 'warning' })
})
```

**Step 2: Run test to verify it fails**

Run: `node --test tests/pipeline-report-presentation.test.js` from `frontend/`.

Expected: FAIL because `reportPresentation.js` does not yet exist.

**Step 3: Write minimal implementation**

```js
export function formatReportDate(value) {
  const [year, month, day] = String(value || '').split('-')
  return year && month && day ? `${year}年${month}月${day}日` : '本期情报'
}

export function getReportStatusMeta(status) {
  return { reviewing: { label: '审核中', type: 'warning' } }[status] || { label: '草稿', type: 'info' }
}
```

**Step 4: Run test to verify it passes**

Run: `node --test tests/pipeline-report-presentation.test.js` from `frontend/`.

Expected: PASS with two passing tests.

### Task 2: 建立管网门户共享设计系统

**Files:**
- Create: `frontend/src/assets/styles/pipeline.scss`
- Modify: `frontend/src/assets/styles/index.scss`
- Modify: `frontend/src/views/pipeline/dashboard/index.vue`
- Modify: `frontend/src/views/pipeline/intelligence/index.vue`
- Modify: `frontend/src/views/pipeline/intelligence/detail.vue`
- Modify: `frontend/src/views/pipeline/source/index.vue`
- Modify: `frontend/src/views/pipeline/task/index.vue`
- Modify: `frontend/src/views/pipeline/knowledge/index.vue`

**Step 1:** Define blue editorial palette, readable typography, page heading, panel, filter, table, tag, focus, dark-mode, reduced-motion and mobile rules in `pipeline.scss`.

**Step 2:** Import the stylesheet after the existing global style imports in `index.scss`.

**Step 3:** Remove duplicated per-page base styles so the shared visual system controls the common `pipeline-page`, `page-heading`, `panel-card`, `table-card`, and status presentation.

**Step 4:** Upgrade the dashboard information hierarchy with labelled metrics, a blue control banner, clearer flow progress and responsive cards without changing its API request or navigation behavior.

**Step 5:** Run `npm run build:prod` from `frontend/`.

Expected: Vite completes with exit code 0.

### Task 3: 将日报周报改造成日报门户阅读界面

**Files:**
- Modify: `frontend/src/views/pipeline/report/index.vue`
- Modify: `frontend/src/utils/pipeline/reportPresentation.js`

**Step 1:** Replace the generic report-card row with a report masthead, edition selector, lead-reading column, report index side column and review list. Keep report generation messages and Markdown export functionality intact.

**Step 2:** Use `formatReportDate` and `getReportStatusMeta` for masthead and report status rendering; preserve `listPipelineReports` as the only report list data source.

**Step 3:** Add keyboard-focus, hover and narrow-screen behavior that does not shift layout; honour `prefers-reduced-motion` via the shared stylesheet.

**Step 4:** Run `node --test tests/pipeline-report-presentation.test.js` and `npm run build:prod` from `frontend/`.

Expected: test suite and production build both exit 0.

### Task 4: Visual smoke verification

**Files:**
- No production source changes required.

**Step 1:** Start the local frontend only if it is not already running, using the documented Vite command.

**Step 2:** Capture the logged-in pipeSight report and dashboard routes at desktop width with headless Edge.

**Step 3:** Inspect screenshots for the reference hierarchy: white masthead/blue editorial accents, readable tables, visible focus/interaction states, no horizontal overflow and usable small-width layout.

**Step 4:** Report the exact verification commands and any intentional scope limits. This workspace is not a Git repository, so no commit step applies.
