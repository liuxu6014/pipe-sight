<template>
  <div class="ps-page">
    <div class="ps-breadcrumb"><button type="button" @click="router.push('/portal/research')">科研工作台</button><span>/</span><b>任务进度</b></div>
    <section class="ps-task-hero"><div><span class="ps-task-state" :class="`is-${task.status}`"><i></i>{{ task.statusLabel || taskStateLabel }}</span><h1>{{ task.title }}</h1><p>{{ reportTypeLabel }} · 创建人：{{ task.owner || currentUserName }} · 创建于 {{ task.createdAt || '刚刚' }}</p></div><div class="ps-task-total"><strong>{{ progress }}%</strong><span>当前阶段：{{ currentStageLabel }}</span></div></section>
    <el-progress :percentage="progress" :stroke-width="10" :show-text="false" class="ps-task-main-progress" />
    <div class="ps-task-layout">
      <section class="ps-panel ps-task-timeline"><div class="ps-section-head"><div><h2>生成阶段</h2></div><span>{{ task.status === 'completed' ? '全部阶段已完成' : task.status === 'cancelled' ? '任务已停止' : '任务状态自动刷新' }}</span></div><div class="ps-stage-list"><div v-for="(stage, index) in stageRows" :key="stage.key || stage.label" :class="{ 'is-complete': stage.status === 'completed', 'is-active': stage.status === 'running' }"><span><Check v-if="stage.status === 'completed'" /><Loading v-else-if="stage.status === 'running'" /><i v-else></i></span><div><strong>{{ stage.label }}</strong><small>{{ stageDescription(index) }}</small></div><time>{{ stage.status === 'completed' ? '已完成' : stage.status === 'running' ? '进行中' : stage.status === 'cancelled' ? '已取消' : '等待中' }}</time></div></div></section>
      <aside class="ps-task-side"><section class="ps-panel"><h3>任务信息</h3><dl><div><dt>使用模板</dt><dd>{{ task.config?.template_id || task.config?.templateId || '平台标准模板' }} {{ task.config?.template_version || task.config?.templateVersion || '' }}</dd></div><div><dt>输入资料</dt><dd>{{ task.selectedItems?.length || 0 }} 条</dd></div><div><dt>目标字数</dt><dd>{{ targetWords.toLocaleString() }} 字</dd></div><div><dt>生成方式</dt><dd>模板与证据编排</dd></div><div><dt>引用检查</dt><dd>{{ task.config?.citation_check === false || task.config?.citationCheck === false ? '未开启' : '已开启' }}</dd></div></dl><p v-if="task.errorMessage" class="ps-task-error">{{ task.errorMessage }}</p></section><section class="ps-panel"><h3>输入资料摘要</h3><div class="ps-input-summary"><span>内部资料 <b>{{ materialCounts.internal }}</b></span><span>论文 <b>{{ materialCounts.paper }}</b></span><span>科技资讯 <b>{{ materialCounts.news }}</b></span></div><el-button text type="primary" @click="showMaterials = true">查看资料清单</el-button></section><div class="ps-task-actions"><el-button v-if="canCancel" :loading="acting" @click="cancelTask">取消任务</el-button><el-button v-else :loading="acting" @click="retryTask">重新生成</el-button><el-button @click="router.push('/portal/research/create')">复制任务</el-button></div></aside>
      <section class="ps-panel ps-task-log"><div class="ps-section-head"><div><h2>实时进展</h2></div><button class="ps-live-dot" type="button"><i></i>{{ task.status === 'completed' ? '已完成' : '自动更新' }}</button></div><div class="ps-log-list"><div v-for="log in logs" :key="`${log.time}-${log.message}`"><time>{{ log.time }}</time><span :class="`is-${log.type}`"></span><p>{{ log.message }}</p></div></div></section>
    </div>
    <div class="ps-sticky-actions"><el-button @click="router.push('/portal/research')">返回工作台</el-button><el-button type="primary" :disabled="!task.reportId" @click="openReport">打开报告</el-button></div>
    <el-dialog v-model="showMaterials" title="输入资料清单" width="680px"><div class="ps-source-check" v-for="item in task.selectedItems || []" :key="item.id"><CircleCheckFilled /><span><strong>{{ item.title }}</strong><small>{{ item.type }} · {{ item.source || '平台知识库' }}</small></span></div><PortalEmptyState v-if="!task.selectedItems?.length" title="没有输入资料" description="该任务没有关联可用资料。" /></el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, CircleCheckFilled, Loading } from '@element-plus/icons-vue'
import useUserStore from '@/store/modules/user'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import { cancelPipelineResearchJob, getPipelineResearchJob, retryPipelineResearchJob } from '@/api/pipeline/intelligence'
import { taskStages } from '../data'
import { getPortalReportPath } from '../utils/routing'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const showMaterials = ref(false)
const acting = ref(false)
const task = ref({ title: '科研生成任务', status: 'running', progress: 0, stages: [], logs: [], selectedItems: [], config: {} })
let refreshTimer
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const progress = computed(() => Number(task.value.progress || 0))
const reportTypeLabel = computed(() => ({ 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表', daily: '日报', weekly: '周报', monthly: '月报' })[task.value.type] || task.value.type || '科研报告')
const taskStateLabel = computed(() => ({ completed: '生成完成', failed: '生成失败', cancelled: '已取消', queued: '等待生成', running: '正在生成' })[task.value.status] || '正在生成')
const canCancel = computed(() => ['queued', 'running'].includes(task.value.status))
const stageRows = computed(() => task.value.stages?.length ? task.value.stages : taskStages.map((label, index) => ({ key: index, label, status: index === 0 ? 'running' : 'waiting' })))
const currentStageLabel = computed(() => stageRows.value.find(item => item.status === 'running')?.label || stageRows.value.filter(item => item.status === 'completed').at(-1)?.label || '准备中')
const logs = computed(() => task.value.logs?.length ? task.value.logs : [{ time: '--:--:--', type: 'info', message: '正在读取任务状态。' }])
const targetWords = computed(() => (task.value.outline || []).reduce((sum, item) => sum + Number(item.words || item.targetWords || 0), 0))
const materialCounts = computed(() => (task.value.selectedItems || []).reduce((result, item) => { const type = String(item.type || ''); if (type.includes('论文')) result.paper += 1; else if (type.includes('资讯') || type.includes('新闻')) result.news += 1; else result.internal += 1; return result }, { internal: 0, paper: 0, news: 0 }))
function stageDescription(index) { return ['确认权限、格式和解析状态', '提取正文、表格与章节结构', '按研究问题检索候选证据', '规划章节、字数与资料覆盖', '逐章生成可编辑内容', '核验引用来源与定位信息', '检查完整性、一致性和风险表述', '准备技术路线与成果图形', '形成可编辑报告与版本记录'][index] || '执行任务阶段' }
async function loadTask() {
  try {
    const res = await getPipelineResearchJob(String(route.params.id))
    task.value = res.data
    if (['completed', 'failed', 'cancelled'].includes(task.value.status)) stopRefresh()
  } catch (error) {
    ElMessage.warning('暂时无法读取任务状态，请确认后端和数据库已启动')
    stopRefresh()
  }
}
function stopRefresh() {
  if (!refreshTimer) return
  clearInterval(refreshTimer)
  refreshTimer = undefined
}
function startRefresh() {
  stopRefresh()
  refreshTimer = setInterval(loadTask, 2000)
}
function openReport() {
  if (!task.value.reportId) return
  router.push(getPortalReportPath({ id: task.value.reportId, reportType: task.value.type }))
}
async function cancelTask() {
  if (acting.value || !canCancel.value) return
  acting.value = true
  try {
    const res = await cancelPipelineResearchJob(String(route.params.id))
    task.value = res.data
    stopRefresh()
    ElMessage.success('任务已取消')
  } catch (error) {
    ElMessage.error(error?.msg || '任务取消失败')
  } finally {
    acting.value = false
  }
}
async function retryTask() {
  if (acting.value) return
  acting.value = true
  try {
    const res = await retryPipelineResearchJob(String(route.params.id))
    task.value = res.data
    startRefresh()
    ElMessage.success('任务已按原配置重新加入生成队列')
  } catch (error) {
    ElMessage.error(error?.msg || '重新生成失败')
  } finally {
    acting.value = false
  }
}
onMounted(() => { loadTask(); startRefresh() })
onUnmounted(stopRefresh)
</script>
