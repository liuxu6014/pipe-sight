<template>
  <div class="ps-page">
    <PortalPageHeader title="科研工作台">
      <template #actions><el-button type="primary" :icon="Plus" @click="router.push('/portal/research/create')">新建科研报告</el-button></template>
    </PortalPageHeader>
    <section class="ps-research-lead">
      <div><span class="ps-eyebrow">从问题到成果</span><h2>选择一个报告类型，开始组织可信证据</h2><p>平台会先校验资料权限与解析状态，再生成大纲、章节、引用和图形。所有内容均可编辑、追溯和版本化。</p></div>
      <aside><span>资料篮</span><strong>{{ portalStore.basketCount }}</strong><small>条已选资料</small><el-button type="primary" plain @click="router.push('/portal/research/create')">使用当前资料创建</el-button></aside>
    </section>
    <section class="ps-template-grid"><button v-for="template in reportTemplates" :key="template.id" type="button" class="ps-template-card" @click="router.push({ path: '/portal/research/create', query: { template: template.id } })"><i :style="{ background: template.color }"></i><span class="ps-template-icon"><Document /></span><span><strong>{{ template.name }}</strong><small>{{ template.description }}</small></span><ArrowRight /></button></section>
    <div class="ps-workbench-grid">
      <section class="ps-panel ps-span-2"><div class="ps-section-head"><div><h2>我的最近报告</h2></div><el-button text @click="router.push('/portal/me/reports')">查看全部</el-button></div><div class="ps-report-table"><div class="ps-table-head"><span>报告名称</span><span>状态</span><span>版本</span><span>更新时间</span><span></span></div><button v-for="report in researchReports" :key="report.id" type="button" @click="router.push(getPortalReportPath(report))"><span><strong>{{ report.title }}</strong><small>{{ report.type }} · {{ report.words ? `${report.words.toLocaleString()} 字` : '字数待统计' }}</small></span><span><b class="ps-status-pill" :class="`is-${statusClass(report.status)}`">{{ report.status }}</b></span><span>{{ report.version }}</span><span>{{ report.updatedAt }}</span><ArrowRight /></button></div></section>
      <section class="ps-panel"><div class="ps-section-head"><div><h2>生成任务</h2></div><button class="ps-live-dot" type="button" @click="portalStore.openTaskPanel()"><i></i>实时</button></div><button v-for="task in portalStore.tasks.slice(0, 4)" :key="task.id" class="ps-workbench-task" type="button" @click="openTask(task)"><span><strong>{{ task.title }}</strong><small>{{ task.statusLabel }}</small></span><el-progress type="circle" :percentage="task.progress" :width="48" :stroke-width="5" /></button></section>
      <section class="ps-panel ps-span-2"><div class="ps-section-head"><div><h2>资料篮</h2></div><el-button v-if="portalStore.basketCount" text type="danger" @click="portalStore.clearBasket()">清空</el-button></div><div v-if="portalStore.basketCount" class="ps-basket-list"><div v-for="item in portalStore.basket" :key="item.id"><span class="ps-file-icon">{{ item.type.slice(0, 1) }}</span><span><strong>{{ item.title }}</strong><small>{{ item.type }}</small></span><button type="button" @click="portalStore.removeFromBasket(item.id)"><Close /></button></div></div><PortalEmptyState v-else title="资料篮还是空的" description="从科技资讯、论文资料或知识库中加入研究材料。" action-label="浏览知识库" @action="router.push('/portal/knowledge')" /></section>
      <section class="ps-panel"><div class="ps-section-head"><div><h2>模板推荐</h2></div></div><div class="ps-recommend-list"><button v-for="template in reportTemplates" :key="template.id" type="button" @click="router.push({ path: '/portal/research/create', query: { template: template.id } })"><span :style="{ background: template.color }"><Document /></span><span><strong>{{ template.name }}</strong><small>默认模板 · 2026版</small></span></button></div></section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Close, Document, Plus } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { reportTemplates } from '../data'
import { getPortalReportPath, getPortalTaskPath } from '../utils/routing'

const router = useRouter()
const portalStore = usePortalStore()
const researchReports = computed(() => portalStore.researchReports)
function openTask(task) { router.push(getPortalTaskPath(task)) }
function statusClass(value) { return ({ '待修改': 'warning', '生成中': 'running', '已完成': 'success', '草稿': 'muted' })[value] || 'muted' }
</script>
