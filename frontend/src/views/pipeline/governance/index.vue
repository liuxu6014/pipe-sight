<template>
  <div class="app-container pipeline-page pipeline-governance-page">
    <div class="pipeline-page-head">
      <div><span class="pipeline-eyebrow">DATA GOVERNANCE</span><h1>数据治理</h1><p class="summary">统一处理重复内容、字段缺失、标签异常和解析失败，保证用户端检索与生成的数据质量。</p></div>
      <div class="pipeline-head-actions"><el-button :icon="Refresh" @click="refreshData">刷新质量扫描</el-button><el-button type="primary" :icon="MagicStick" @click="runBatch">执行批量治理</el-button></div>
    </div>

    <div class="pipeline-metric-grid governance-metrics">
      <article v-for="metric in metrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small :class="`is-${metric.type}`">{{ metric.hint }}</small></article>
    </div>

    <el-card shadow="never" class="pipeline-card">
      <div class="governance-toolbar"><el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索标题、来源或异常说明" /><el-select v-model="issueType"><el-option label="全部问题" value="all" /><el-option label="重复内容" value="duplicate" /><el-option label="字段缺失" value="missing" /><el-option label="标签异常" value="tag" /><el-option label="解析失败" value="parse" /></el-select><el-select v-model="status"><el-option label="全部状态" value="all" /><el-option label="待处理" value="pending" /><el-option label="处理中" value="processing" /><el-option label="已解决" value="resolved" /></el-select></div>
      <el-table :data="filteredRows" row-key="id">
        <el-table-column type="selection" width="48" />
        <el-table-column label="内容记录" min-width="300"><template #default="{ row }"><div class="governance-record"><strong>{{ row.title }}</strong><small>{{ row.source }} · {{ row.time }}</small></div></template></el-table-column>
        <el-table-column label="问题类型" width="110"><template #default="{ row }"><el-tag :type="issueTag(row.type)" effect="light">{{ row.issue }}</el-tag></template></el-table-column>
        <el-table-column prop="description" label="异常说明" min-width="240" show-overflow-tooltip />
        <el-table-column label="质量评分" width="120"><template #default="{ row }"><el-progress :percentage="row.score" :color="scoreColor(row.score)" /></template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="statusTag(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="170" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openDrawer(row)">处理</el-button><el-button link @click="ElMessage.info('已打开原始记录')">原始记录</el-button><el-button link @click="resolveRow(row)">标记解决</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="治理处理" size="520px">
      <template v-if="activeRow"><el-descriptions :column="1" border><el-descriptions-item label="记录标题">{{ activeRow.title }}</el-descriptions-item><el-descriptions-item label="问题类型">{{ activeRow.issue }}</el-descriptions-item><el-descriptions-item label="异常说明">{{ activeRow.description }}</el-descriptions-item></el-descriptions><div class="governance-drawer-section"><h3>处理建议</h3><el-radio-group v-model="resolution"><el-radio value="merge">合并至主记录</el-radio><el-radio value="repair">补全字段并重新索引</el-radio><el-radio value="ignore">保留并忽略本次问题</el-radio></el-radio-group><el-input v-model="note" type="textarea" :rows="4" placeholder="填写处理说明" /></div></template>
      <template #footer><el-button @click="drawerVisible = false">取消</el-button><el-button type="primary" @click="submitResolution">确认处理</el-button></template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh, Search } from '@element-plus/icons-vue'

const keyword = ref('')
const issueType = ref('all')
const status = ref('all')
const drawerVisible = ref(false)
const activeRow = ref(null)
const resolution = ref('repair')
const note = ref('')
const metrics = [{ label: '今日入库', value: '1,286', hint: '较昨日 +8.4%', type: 'success' }, { label: '待治理', value: '47', hint: '12 条高优先级', type: 'warning' }, { label: '重复事件', value: '16', hint: '可合并为 7 组', type: 'warning' }, { label: '平均质量分', value: '92.6', hint: '目标 ≥ 90', type: 'success' }]
const rows = ref([{ id: 1, title: '管道多元检测数据智能化分析进入工程化验证阶段', source: '能源科技观察', time: '2026-08-04 09:30', type: 'duplicate', issue: '重复内容', description: '与微信公众号转载稿相似度 96.8%', score: 78, status: 'pending' }, { id: 2, title: '油气管道应力监测向在线化持续演进', source: '管道技术前沿', time: '2026-08-03 16:20', type: 'missing', issue: '字段缺失', description: '缺少作者、原文发布时间和封面图字段', score: 72, status: 'processing' }, { id: 3, title: 'Pipeline Integrity Recommended Practice 2026', source: '内部上传', time: '2026-08-03 11:06', type: 'parse', issue: '解析失败', description: '第 42-45 页表格结构识别失败', score: 64, status: 'pending' }, { id: 4, title: '智能阴极保护系统异常诊断应用', source: '腐蚀与防护学会', time: '2026-08-01 14:35', type: 'tag', issue: '标签异常', description: '技术方向标签与正文主题匹配度低', score: 83, status: 'resolved' }])
const filteredRows = computed(() => rows.value.filter(row => (issueType.value === 'all' || row.type === issueType.value) && (status.value === 'all' || row.status === status.value) && (!keyword.value || `${row.title}${row.source}${row.description}`.includes(keyword.value))))
function issueTag(type) { return ({ duplicate: 'warning', missing: 'danger', parse: 'danger', tag: 'info' })[type] || 'info' }
function statusTag(value) { return ({ pending: 'warning', processing: 'primary', resolved: 'success' })[value] }
function statusLabel(value) { return ({ pending: '待处理', processing: '处理中', resolved: '已解决' })[value] }
function scoreColor(value) { return value >= 90 ? '#14845d' : value >= 75 ? '#d18a33' : '#c64040' }
function openDrawer(row) { activeRow.value = row; drawerVisible.value = true }
function resolveRow(row) { row.status = 'resolved'; ElMessage.success('已标记为解决') }
function submitResolution() { if (activeRow.value) activeRow.value.status = 'resolved'; drawerVisible.value = false; ElMessage.success('治理结果已保存并进入重新索引队列') }
function refreshData() { ElMessage.success('质量扫描已刷新') }
function runBatch() { ElMessage.success('批量治理任务已创建') }
</script>

<style scoped>
.governance-metrics { margin-bottom: 18px; }
.governance-metrics article { padding: 22px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }
.governance-metrics span,.governance-metrics small { color: #64748b; font-size: 12px; }
.governance-metrics strong { margin: 8px 0 4px; display: block; color: #0f172a; font-size: 28px; }
.governance-metrics small.is-success { color: #14845d; }.governance-metrics small.is-warning { color: #b66a20; }
.governance-toolbar { margin-bottom: 16px; display: grid; grid-template-columns: minmax(280px,1fr) 160px 140px; gap: 10px; }
.governance-record { display: flex; flex-direction: column; }.governance-record small { margin-top: 5px; color: #64748b; font-size: 11px; }
.governance-drawer-section { margin-top: 22px; display: grid; gap: 16px; }.governance-drawer-section h3 { margin: 0; }.governance-drawer-section .el-radio-group { display: flex; align-items: flex-start; flex-direction: column; gap: 10px; }
@media (max-width: 760px) { .governance-toolbar { grid-template-columns: 1fr; } }
</style>
