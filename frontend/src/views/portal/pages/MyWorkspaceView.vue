<template>
  <div class="ps-page">
    <PortalPageHeader :title="pageConfig.title" :description="pageConfig.description">
      <template #actions><el-button v-if="mode === 'tasks'" type="primary" @click="router.push('/portal/research/create')"><Plus />新建任务</el-button><el-button v-else-if="mode === 'reports'" type="primary" @click="router.push('/portal/research/create')"><Plus />新建报告</el-button></template>
    </PortalPageHeader>
    <div v-if="mode === 'tasks'" class="ps-my-task-grid"><article v-for="task in portalStore.tasks" :key="task.id" class="ps-my-task-card"><div><span class="ps-task-status" :class="`is-${task.status}`"></span><span><strong>{{ task.title }}</strong><small>{{ task.type }} · {{ task.updatedAt }}</small></span><b>{{ task.statusLabel }}</b></div><el-progress :percentage="task.progress" :stroke-width="7" /><footer><span>{{ taskHint(task) }}</span><el-button type="primary" text @click="openTask(task)">{{ taskActionLabel(task) }}</el-button></footer></article><PortalEmptyState v-if="!portalStore.tasks.length" title="当前没有任务" description="创建科研报告或情报简报后，可在这里跟踪生成进度。" action-label="新建任务" @action="router.push('/portal/research/create')" /></div>
    <section v-else-if="mode === 'reports'" class="ps-report-table ps-panel"><div class="ps-table-head"><span>成果名称</span><span>状态</span><span>版本</span><span>字数</span><span>更新时间</span><span></span></div><button v-for="report in allReports" :key="report.id" type="button" @click="router.push(getPortalReportPath(report))"><span><strong>{{ report.title }}</strong><small>{{ report.type }}</small></span><span><b class="ps-status-pill">{{ report.status }}</b></span><span>{{ report.version }}</span><span>{{ report.words ? report.words.toLocaleString() : '待统计' }}</span><span>{{ report.updatedAt }}</span><ArrowRight /></button><PortalEmptyState v-if="!allReports.length" title="当前没有成果" description="创建科研报告或情报简报后，可在这里继续编辑并查看历史版本。" action-label="新建科研报告" @action="router.push('/portal/research/create')" /></section>
    <section v-else><div v-if="favoriteItems.length" class="ps-favorite-grid"><article v-for="item in favoriteItems" :key="item.id"><span>{{ item.type }}</span><button type="button" @click="router.push(item.path)">{{ item.title }}</button><p>{{ item.summary }}</p><footer><el-button type="primary" text @click="router.push(item.path)">打开详情</el-button><el-button text type="danger" @click="portalStore.toggleFavorite(item.id)">取消收藏</el-button></footer></article></div><PortalEmptyState v-else title="还没有收藏内容" description="在科技资讯和论文详情页收藏的内容会集中显示在这里。" action-label="浏览科技资讯" @action="router.push('/portal/news')" /></section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Plus } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPortalReportPath, getPortalTaskPath } from '../utils/routing'

const props = defineProps({ mode: { type: String, default: 'tasks' } })
const router = useRouter()
const portalStore = usePortalStore()
const pageConfig = computed(() => ({ tasks: { title: '我的任务', description: '集中跟踪科研生成、周期简报、资料解析和导出任务。' }, reports: { title: '我的报告', description: '查看本人创建和参与编辑的科研报告及版本状态。' }, favorites: { title: '我的收藏', description: '集中保存需要持续跟踪的科技资讯和论文。' } })[props.mode])
const researchReports = computed(() => portalStore.researchReports)
const allReports = computed(() => [...portalStore.researchReports, ...portalStore.digestReports].sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''))))
const favoriteItems = computed(() => [
  ...portalStore.newsItems.map(item => ({ ...item, type: '科技资讯', path: `/portal/news/${item.id}` })),
  ...portalStore.paperItems.map(item => ({ ...item, title: item.titleZh, summary: item.abstract, type: '论文', path: `/portal/papers/${item.id}` })),
  ...portalStore.knowledgeDocuments.map(item => ({ ...item, title: item.name, type: '内部资料', path: `/portal/knowledge/${item.id}` })),
  ...portalStore.researchReports.map(item => ({ ...item, summary: `${item.type} · ${item.status}`, path: getPortalReportPath(item) })),
  ...portalStore.digestReports.map(item => ({ ...item, summary: `${item.type} · ${item.status}`, path: getPortalReportPath(item) }))
].filter(item => portalStore.favorites.includes(item.id)))
function openTask(task) { router.push(getPortalTaskPath(task)) }
function taskActionLabel(task) { return task.status === 'completed' && task.reportId ? '查看结果' : ['failed', 'cancelled'].includes(task.status) ? '查看详情' : '查看进度' }
function taskHint(task) {
  if (task.status === 'completed') return task.reportId ? '任务已完成，可查看结果' : '任务已完成'
  if (task.status === 'failed') return '生成失败，可查看原因并重新生成'
  if (task.status === 'cancelled') return '任务已取消，可按原配置重新生成'
  return `当前进度 ${task.progress}%`
}
</script>
