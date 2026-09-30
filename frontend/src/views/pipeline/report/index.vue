<template>
  <div class="pipeline-page pipeline-report-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 报告审核</p>
        <h1>日报周月报与科研报告</h1>
        <p class="summary">后台负责报告生成、人工审核、导出和发布；用户端报告阅读入口已移至 /portal。</p>
      </div>
      <div class="heading-actions">
        <el-button plain :icon="DocumentAdd" @click="showComingSoon('新建报告')">新建报告</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadReports">刷新本期</el-button>
      </div>
    </section>

    <section class="report-masthead" aria-label="报告阅读导航">
      <div class="report-brand">
        <div class="report-brand-mark">PI</div>
        <div><b>国家管网科技情报与科研辅助平台</b><span>PIPELINE INTELLIGENCE BRIEF</span></div>
      </div>
      <div class="report-controls">
        <el-radio-group v-model="editionType" size="small" aria-label="报告类型">
          <el-radio-button label="日报" />
          <el-radio-button label="周报" />
          <el-radio-button label="月报" />
          <el-radio-button label="专项" />
        </el-radio-group>
        <span class="edition-date">{{ formatReportDate(selectedReport?.updated_at) }}</span>
      </div>
    </section>

    <nav class="report-section-nav" aria-label="报告操作">
      <button v-for="item in reportTypes" :key="item.title" type="button" @click="showComingSoon(`${item.title}生成`)">
        <el-icon><component :is="item.icon" /></el-icon>{{ item.title }}<el-icon><ArrowRight /></el-icon>
      </button>
    </nav>

    <section v-loading="loading" class="report-reading">
      <article class="report-lead">
        <span class="lead-caption">本期主报告 · {{ editionType }}</span>
        <h2>{{ selectedReport?.title || '正在汇集本期管网科技情报' }}</h2>
        <div class="lead-meta">
          <span>{{ selectedReport?.type || '科技情报日报' }}</span>
          <span>责任组：{{ selectedReport?.owner || '情报研判组' }}</span>
          <span>{{ selectedReport?.updated_at || '数据加载中' }}</span>
        </div>
        <p class="lead-summary">本期报告覆盖重点技术方向、行业动态与科研需求线索。系统已完成来源汇聚与结构化处理，提交人工审核后即可形成正式发布版本。</p>
        <div class="report-highlights">
          <div><span>覆盖资讯</span><b>{{ selectedReport?.coverage ?? '--' }}</b><em>条有效情报</em></div>
          <div><span>审核状态</span><el-tag :type="getReportStatusMeta(selectedReport?.status).type" effect="light">{{ getReportStatusMeta(selectedReport?.status).label }}</el-tag><em>人工复核可追溯</em></div>
          <div><span>输出格式</span><b>MD</b><em>支持归档与再编辑</em></div>
        </div>
        <div class="lead-actions">
          <el-button type="primary" :icon="Download" :disabled="!selectedReport" :loading="downloadingReportId === selectedReport?.id" @click="handleExportReport(selectedReport)">导出本期 Markdown</el-button>
          <el-button :icon="Edit" @click="showComingSoon('报告编辑')">进入审核编排</el-button>
        </div>
      </article>

      <aside class="report-index">
        <div class="index-heading"><span>本期报告索引</span><small>{{ rows.length }} 份</small></div>
        <button v-for="(row, index) in rows" :key="row.id" :class="{ active: selectedReport?.id === row.id }" type="button" @click="activeReportId = row.id">
          <span class="index-number">0{{ index + 1 }}</span>
          <span class="index-copy"><b>{{ row.title }}</b><em>{{ row.type }} · {{ getReportStatusMeta(row.status).label }}</em></span>
          <el-icon><ArrowRight /></el-icon>
        </button>
        <div v-if="!loading && !rows.length" class="index-empty">暂无可阅读的报告草稿</div>
      </aside>
    </section>

    <el-card shadow="never" class="table-card report-review-table">
      <template #header><div class="card-header"><span>报告审核清单</span><span class="table-caption">REVIEW QUEUE</span></div></template>
      <el-table v-loading="loading" :data="rows" border>
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="150" />
        <el-table-column prop="owner" label="责任组" width="140" />
        <el-table-column prop="coverage" label="覆盖资讯" width="110" align="right" />
        <el-table-column prop="status" label="状态" width="120"><template #default="{ row }"><el-tag :type="getReportStatusMeta(row.status).type" effect="light">{{ getReportStatusMeta(row.status).label }}</el-tag></template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" />
        <el-table-column label="操作" width="165" fixed="right"><template #default="{ row }"><el-button link type="primary" :icon="Edit" @click="showComingSoon('报告编辑')">编辑</el-button><el-button link type="primary" :icon="Download" :loading="downloadingReportId === row.id" @click="handleExportReport(row)">导出</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Calendar, DocumentAdd, Download, Edit, Files, Notebook, Refresh } from '@element-plus/icons-vue'
import { exportPipelineReport, listPipelineReports } from '@/api/pipeline/intelligence'
import { formatReportDate, getReportStatusMeta } from '@/utils/pipeline/reportPresentation'

defineOptions({ name: 'PipelineReport' })

const loading = ref(false)
const downloadingReportId = ref('')
const rows = ref([])
const activeReportId = ref('')
const editionType = ref('日报')
const reportTypes = [
  { title: '科技情报日报', icon: markRaw(Notebook) },
  { title: '科技情报月报', icon: markRaw(Calendar) },
  { title: '技术路线报告', icon: markRaw(Files) },
  { title: '科研需求报告', icon: markRaw(DocumentAdd) }
]
const selectedReport = computed(() => rows.value.find(item => item.id === activeReportId.value) || rows.value[0])

async function loadReports() {
  loading.value = true
  try {
    const res = await listPipelineReports()
    rows.value = res.data.rows
    if (!activeReportId.value && rows.value.length) activeReportId.value = rows.value[0].id
  } catch (error) {
    ElMessage.warning('暂时无法获取报告列表')
  } finally {
    loading.value = false
  }
}

function downloadMarkdown(fileName, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName || '管网科技情报报告.md'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function handleExportReport(row) {
  if (!row) return
  downloadingReportId.value = row.id
  try {
    const res = await exportPipelineReport(row.id)
    downloadMarkdown(res.data.file_name, res.data.content)
    ElMessage.success('报告已导出')
  } catch (error) {
    ElMessage.warning('报告导出失败，请稍后重试')
  } finally {
    downloadingReportId.value = ''
  }
}

function showComingSoon(action) {
  ElMessage.info(`${action}将在下一阶段接入完整审核流`)
}

onMounted(loadReports)
</script>

<style scoped>
.heading-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.report-masthead { display: flex; justify-content: space-between; gap: 20px; align-items: center; padding: 22px 24px; border: 1px solid #d9e2e9; background: #fff; }
.report-brand { display: flex; align-items: center; gap: 12px; }
.report-brand-mark { width: 42px; height: 42px; display: grid; place-items: center; color: #fff; background: #005487; font-weight: 800; }
.report-brand b, .report-brand span { display: block; }
.report-brand span, .edition-date, .table-caption { color: #68798a; font-size: 12px; letter-spacing: .08em; }
.report-controls { display: flex; align-items: flex-end; flex-direction: column; gap: 8px; }
.report-section-nav { display: flex; margin-bottom: 18px; border-right: 1px solid #d9e2e9; border-left: 1px solid #d9e2e9; background: #fff; }
.report-section-nav button { flex: 1; min-width: 185px; height: 50px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; border: 0; border-right: 1px solid #e4eaee; background: transparent; color: #173d56; cursor: pointer; font-weight: 650; }
.report-reading { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; margin-bottom: 18px; }
.report-lead, .report-index { border: 1px solid #d9e2e9; background: #fff; padding: 24px; }
.lead-caption { color: #005487; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.report-lead h2 { margin: 10px 0; color: #173d56; font-size: 28px; }
.lead-meta, .lead-summary { color: #526b7d; line-height: 1.8; }
.lead-meta { display: flex; flex-wrap: wrap; gap: 10px 18px; font-size: 13px; }
.report-highlights { display: grid; grid-template-columns: repeat(3, 1fr); margin: 20px 0; border: 1px solid #e0e8ed; }
.report-highlights > div { padding: 16px; border-right: 1px solid #e0e8ed; }
.report-highlights span, .report-highlights em { display: block; color: #718799; font-size: 12px; font-style: normal; }
.report-highlights b { display: block; margin: 8px 0; color: #173d56; font-size: 28px; }
.lead-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.index-heading, .report-index > button { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-index > button { width: 100%; padding: 14px 0; border: 0; border-top: 1px solid #e2e8ee; background: transparent; text-align: left; cursor: pointer; }
.index-number { color: #005487; font-weight: 700; }
.index-copy { flex: 1; min-width: 0; }
.index-copy b, .index-copy em { display: block; }
.index-copy em { margin-top: 4px; color: #7a8796; font-size: 12px; font-style: normal; }
.index-empty { padding-top: 18px; color: #7a8796; font-size: 13px; }
@media (max-width: 860px) { .report-reading { grid-template-columns: 1fr; }.report-controls { align-items: flex-start; } }
@media (max-width: 640px) { .report-masthead { align-items: flex-start; flex-direction: column; gap: 16px; }.report-section-nav { flex-wrap: wrap; overflow-x: visible; }.report-section-nav button { flex: 1 1 50%; min-width: 0; padding: 12px 8px; border-bottom: 1px solid #e4eaee; }.report-section-nav button:last-child { flex-basis: 100%; border-bottom: 0; }.report-highlights { grid-template-columns: 1fr; }.report-highlights > div { border-right: 0; border-bottom: 1px solid #e0e8ed; } }
</style>
