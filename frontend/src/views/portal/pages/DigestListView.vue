<template>
  <div class="ps-page">
    <PortalPageHeader title="简报管理">
      <template #actions><el-button type="primary" :icon="Plus" @click="router.push('/portal/digests/create')">新建简报</el-button></template>
    </PortalPageHeader>
    <div class="ps-toolbar"><div class="ps-search-inline"><Search /><input v-model="keyword" placeholder="搜索报告标题" /></div><el-date-picker v-model="date" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" /><el-select v-model="status" style="width: 130px"><el-option label="全部状态" value="all" /><el-option label="草稿" value="草稿" /><el-option label="待审核" value="待审核" /><el-option label="已完成" value="已完成" /></el-select></div>
    <div class="ps-tabs-line"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
    <section class="ps-digest-grid">
      <article v-for="report in filteredReports" :key="report.id" class="ps-digest-card"><div class="ps-digest-cover" :class="`is-${typeClass(report.type)}`"><span>{{ report.type }}</span><strong>{{ report.period }}</strong><i></i></div><div class="ps-digest-body"><div class="ps-digest-state"><span class="ps-status-pill" :class="`is-${statusClass(report.status)}`">{{ report.status }}</span><small>{{ report.version }}</small></div><button type="button" @click="router.push(`/portal/digests/${report.id}`)">{{ report.title }}</button><dl><div><dt>覆盖周期</dt><dd>{{ report.period }}</dd></div><div><dt>来源数量</dt><dd>{{ report.sources }} 个</dd></div><div><dt>更新时间</dt><dd>{{ report.updatedAt }}</dd></div></dl><div class="ps-card-actions"><el-button type="primary" text @click="router.push(`/portal/digests/${report.id}`)">查看 / 编辑</el-button><el-dropdown><el-button text :aria-label="`${report.title}更多操作`"><MoreFilled /></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :disabled="exportingId === report.id" @click="exportDigest(report)">{{ exportingId === report.id ? '正在导出…' : '导出 Markdown' }}</el-dropdown-item><el-dropdown-item @click="openSources(report)">打开来源清单</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></div></article>
      <PortalEmptyState v-if="!filteredReports.length" title="没有匹配的情报简报" description="请调整类型、状态、日期或标题关键词。" />
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { exportPipelineResearchReport } from '@/api/pipeline/intelligence'

const router = useRouter()
const portalStore = usePortalStore()
const keyword = ref('')
const date = ref([])
const status = ref('all')
const activeTab = ref('全部')
const exportingId = ref('')
const tabs = ['全部', '日报', '周报', '月报', '自动任务']
const filteredReports = computed(() => portalStore.digestReports.filter(item => {
  const matchesDate = !date.value?.length || isWithinDateRange(item, date.value)
  return (activeTab.value === '全部' || item.type === activeTab.value) && (status.value === 'all' || item.status === status.value) && (!keyword.value || item.title.includes(keyword.value)) && matchesDate
}))
function typeClass(value) { return ({ '日报': 'daily', '周报': 'weekly', '月报': 'monthly', '自动任务': 'auto' })[value] || 'daily' }
function statusClass(value) { return ({ '已完成': 'success', '待审核': 'warning', '草稿': 'muted', '运行中': 'running' })[value] || 'muted' }
function reportDate(report) {
  const candidate = report.updated_at || report.updatedAt || report.period || ''
  return String(candidate).match(/\d{4}-\d{2}-\d{2}/)?.[0] || ''
}
function isWithinDateRange(report, range) {
  const value = reportDate(report)
  return value ? value >= range[0] && value <= range[1] : false
}
function openSources(report) { router.push({ path: `/portal/digests/${report.id}`, query: { panel: 'sources' } }) }
async function exportDigest(report) {
  exportingId.value = report.id
  try {
    const res = await exportPipelineResearchReport(report.id)
    const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = res.data.fileName || `${report.title}.md`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('情报简报已导出')
  } catch (error) {
    ElMessage.error('导出失败，请确认报告已保存且后端服务可用')
  } finally {
    exportingId.value = ''
  }
}
</script>
