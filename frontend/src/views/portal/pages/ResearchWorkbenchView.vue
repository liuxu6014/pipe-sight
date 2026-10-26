<template>
  <div class="ps-page ps-research-workspace">
    <div class="ps-toolbar ps-research-toolbar">
        <el-input class="ps-search-input" v-model.trim="keyword" clearable aria-label="搜索报告" placeholder="搜索报告名称或类型" :prefix-icon="Search" />
        <el-select v-model="status" placeholder="全部状态" aria-label="报告生成状态"><el-option label="全部状态" value="" /><el-option v-for="item in reportStatuses" :key="item.value" :label="item.label" :value="item.value" /></el-select>
        <el-select v-model="sort" aria-label="报告排序"><el-option label="最近更新" value="updated-desc" /><el-option label="最早更新" value="updated-asc" /><el-option label="名称排序" value="title" /></el-select>
        <el-button v-if="keyword || status" @click="keyword = ''; status = ''">重置</el-button>
      <div class="ps-research-toolbar-actions"><el-button type="primary" :icon="Plus" @click="router.push('/portal/research/create')">新建报告</el-button></div>
    </div>
    <div class="ps-report-workspace-content">
      <section class="ps-panel ps-report-main">
        <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}</span><el-button text @click="portalStore.hydrate(true)">重试</el-button></div>
        <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="5" animated />
        <template v-else>
          <div v-if="filteredReports.length" class="ps-report-table">
            <div class="ps-table-head"><span>报告名称</span><span>状态</span><span>版本</span><span>更新时间</span><span></span></div>
            <button v-for="report in pagedReports" :key="report.key" type="button" :aria-label="`打开报告：${report.title}`" @click="router.push(report.path)"><span><strong>{{ report.title }}</strong><small>{{ report.typeLabel }}<template v-if="report.businessStatus"> · {{ report.businessStatus }}</template><template v-if="report.words"> · {{ Number(report.words).toLocaleString() }} 字</template><template v-if="report.status === 'failed'"> · 查看原因 / 重试</template></small><el-progress v-if="report.status === 'active'" :percentage="report.progress" :stroke-width="4" /></span><span><b class="ps-status-pill" :class="`is-${statusClass(report.status)}`">{{ report.statusLabel }}</b></span><span>{{ report.version || '—' }}</span><span>{{ report.updatedAt || '时间未提供' }}</span><ArrowRight /></button>
          </div>
          <div v-else-if="!loadError" class="ps-empty-state" role="status">{{ keyword || status ? '暂无匹配报告' : '暂无报告' }}</div>
          <div v-if="filteredReports.length" class="ps-pagination" aria-label="科研报告列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="filteredReports.length" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Plus, Search } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { buildPersonalReports } from '@/utils/portal/personalReports'
import useUserStore from '@/store/modules/user'
import { sortResearchReports } from '../utils/reportList'

const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const userStore = useUserStore()
const researchReports = computed(() => buildPersonalReports({ reports: [...portalStore.researchReports, ...portalStore.digestReports], tasks: portalStore.tasks, userId: userStore.id }))
const keyword = ref(String(route.query.q || ''))
const normalizeStatus = value => value === 'completed' ? 'generated' : ['active', 'generated', 'failed', 'cancelled'].includes(value) ? value : ''
const status = ref(normalizeStatus(route.query.status))
watch(() => route.query, query => { keyword.value = String(query.q || ''); status.value = normalizeStatus(query.status) })
const currentPage = ref(1)
const pageSize = ref(10)
const sort = ref('updated-desc')
const reportStatuses = [{ value: 'active', label: '生成中' }, { value: 'generated', label: '已生成' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' }]
const loadError = computed(() => portalStore.sectionErrors.reports || portalStore.sectionErrors.tasks || portalStore.sectionErrors.digests)
const filteredReports = computed(() => researchReports.value.filter(item => (!status.value || item.status === status.value) && (!keyword.value || `${item.title} ${item.typeLabel}`.toLocaleLowerCase().includes(keyword.value.toLocaleLowerCase()))))
const pagedReports = computed(() => sortResearchReports(filteredReports.value, sort.value).slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([keyword, status, sort, pageSize], () => { currentPage.value = 1 })
watch(() => filteredReports.value.length, count => { currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(count / pageSize.value))) })
function statusClass(value) { return ({ active: 'running', generated: 'success', failed: 'danger', cancelled: 'muted' })[value] || 'muted' }
</script>

<style scoped>
.ps-research-toolbar-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.ps-research-toolbar-actions :deep(.el-button) { margin-left: 0; }
@media (min-width: 1051px) {
  .ps-research-toolbar > .el-input { flex: 1 1 180px; }
  .ps-research-toolbar > .el-select { flex: 0 0 130px; width: 130px; }
}
</style>
