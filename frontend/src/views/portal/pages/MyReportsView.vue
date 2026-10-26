<template>
  <div class="ps-page ps-personal-reports">
    <div class="ps-workspace-filter">
      <el-input class="ps-search-input" v-model.trim="query.q" clearable aria-label="搜索我的报告" placeholder="搜索报告名称或类型" />
      <el-button v-if="query.q || query.status !== 'all'" @click="query.q = ''; query.status = 'all'">清除筛选</el-button>
    </div>
    <div class="ps-personal-status" role="group" aria-label="报告生成状态">
      <button v-for="tab in statusTabs" :key="tab.value" type="button" :aria-pressed="query.status === tab.value" @click="query.status = tab.value">{{ tab.label }}<span>{{ tab.count }}</span></button>
    </div>
    <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>部分报告记录未加载，以下仅显示已加载记录。</span><el-button text :loading="store.dataLoading" @click="store.hydrate(true)">重新加载</el-button></div>
    <el-skeleton v-if="store.dataLoading && !store.dataLoaded" :rows="5" animated />
    <template v-else>
      <section class="ps-personal-report-list" aria-label="我的报告列表">
        <article v-for="row in visibleRows" :key="row.key" class="ps-panel ps-personal-report-row">
          <div class="ps-personal-report-heading"><button type="button" @click="router.push(row.path)">{{ row.title }}</button><span class="ps-status-pill" :class="`is-${row.status}`">{{ row.statusLabel }}</span></div>
          <div class="ps-personal-report-meta"><span>{{ row.typeLabel }}</span><span v-if="row.businessStatus">{{ row.businessStatus }}</span><span v-if="row.version">版本 {{ row.version }}</span><span v-if="row.words">{{ Number(row.words).toLocaleString() }} 字</span><time>{{ row.updatedAt || '更新时间未提供' }}</time></div>
          <el-progress v-if="row.status === 'active'" :percentage="row.progress" :stroke-width="6" />
          <footer><small>{{ rowHint(row) }}</small><div><el-button v-if="row.taskPath" text @click="router.push(row.taskPath)">生成记录</el-button><el-button type="primary" plain @click="router.push(row.path)">{{ rowAction(row) }}</el-button></div></footer>
        </article>
      </section>
      <PortalEmptyState v-if="!visibleRows.length && !loadError" :title="query.q || query.status !== 'all' ? '没有匹配记录' : '还没有报告记录'" :description="query.q || query.status !== 'all' ? '请调整关键词或生成状态。' : '科研报告与情报简报的生成进度、失败记录和结果都在这里查看。'" />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import { useListQuery } from '@/utils/portal/listQuery'
import { buildPersonalReports } from '@/utils/portal/personalReports'

const router = useRouter()
const store = usePortalStore()
const user = useUserStore()
const query = useListQuery({ q: '', status: 'all' })
const rows = computed(() => buildPersonalReports({ reports: [...store.researchReports, ...store.digestReports], tasks: store.tasks, userId: user.id }))
const statusTabs = computed(() => [
  { value: 'all', label: '全部' }, { value: 'active', label: '生成中' }, { value: 'generated', label: '已生成' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' }
].map(tab => ({ ...tab, count: rows.value.filter(row => tab.value === 'all' || row.status === tab.value).length })))
const visibleRows = computed(() => rows.value.filter(row => (query.status === 'all' || row.status === query.status) && (!query.q || `${row.title} ${row.typeLabel}`.toLocaleLowerCase().includes(query.q.toLocaleLowerCase()))))
const loadError = computed(() => store.sectionErrors?.tasks || store.sectionErrors?.reports || store.sectionErrors?.digests)
function rowAction(row) { return row.hasOutput ? '编辑 / 导出' : row.status === 'failed' ? '查看原因 / 重试' : row.status === 'cancelled' ? '查看 / 重新生成' : row.status === 'generated' ? '查看生成记录' : '查看进度' }
function rowHint(row) {
  if (row.hasOutput) return row.requiresReview ? '已生成草稿，需复核后使用。' : '可查看、编辑和导出；发布状态以报告详情为准。'
  return ({ active: `当前进度 ${row.progress}%`, failed: '查看失败原因后可重新生成。', cancelled: '已取消，可按原配置重新生成。', generated: '任务已完成，结果记录尚未同步，可进入生成记录查看。' })[row.status]
}
onMounted(() => store.hydrate())
</script>

<style scoped>
.ps-personal-status { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 16px; }
.ps-personal-status button { display: flex; align-items: center; gap: 8px; min-height: 40px; padding: 8px 14px; border: 1px solid var(--ps-line); border-radius: 7px; background: #fff; color: var(--ps-muted); font: inherit; cursor: pointer; }
.ps-personal-status button[aria-pressed="true"] { background: var(--ps-blue-soft); color: var(--ps-blue); border-color: #b8d3e3; }
.ps-personal-status button span { font-size: 12px; font-variant-numeric: tabular-nums; }
.ps-personal-report-list { display: grid; gap: 12px; }
.ps-personal-report-row { padding: 20px 24px; min-width: 0; }
.ps-personal-report-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.ps-personal-report-heading > button { padding: 0; border: 0; background: transparent; color: var(--ps-ink); font: inherit; font-size: 17px; font-weight: 600; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.ps-personal-report-heading > span { flex-shrink: 0; }
.ps-status-pill.is-failed { color: #a43333; background: #fff0f0; }
.ps-status-pill.is-active { color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-personal-report-meta { display: flex; flex-wrap: wrap; gap: 5px 16px; margin: 10px 0; color: var(--ps-muted); font-size: 13px; }
.ps-personal-report-row footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; }
.ps-personal-report-row footer small { color: var(--ps-muted); line-height: 1.6; }
.ps-personal-report-row footer > div { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }
.ps-personal-report-row footer :deep(.el-button) { margin-left: 0; }
@media (max-width: 600px) {
  .ps-personal-status button { min-height: 44px; padding-inline: 12px; }
  .ps-personal-report-row { padding: 16px; }
  .ps-personal-report-row footer { align-items: flex-start; flex-direction: column; }
  .ps-personal-report-row footer > div { flex-shrink: 1; }
}
</style>
