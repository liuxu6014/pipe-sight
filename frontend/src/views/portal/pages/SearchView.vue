<template>
  <div class="ps-page">
    <PortalPageHeader title="全局搜索">
      <template #actions><el-button @click="clearFilters">清除筛选</el-button></template>
    </PortalPageHeader>

    <div class="ps-search-mode" role="group" aria-label="检索方式"><button type="button" :aria-pressed="searchMode === 'keyword'" :class="{ 'is-active': searchMode === 'keyword' }" @click="searchMode = 'keyword'">关键词搜索</button><button type="button" :aria-pressed="searchMode === 'semantic'" :class="{ 'is-active': searchMode === 'semantic' }" @click="searchMode = 'semantic'">语义搜索<span>待接入</span></button></div>
    <form class="ps-search-hero" @submit.prevent="applyKeyword">
      <Search />
      <input v-model.trim="draftKeyword" maxlength="200" aria-label="全站搜索关键词" :placeholder="searchMode === 'semantic' ? '用自然语言描述你想研究的问题' : '输入题名、作者、摘要或资料名称'" />
      <el-button native-type="submit" type="primary">{{ searchMode === 'semantic' ? '语义搜索' : '搜索' }}</el-button>
    </form>

    <section v-if="searchMode === 'semantic'" class="ps-semantic-pending ps-panel" role="status"><Search /><h2>语义搜索待接入</h2><p>你输入的问题已保留。接入向量模型并建立资料索引后，系统将按内容含义匹配研究线索，而不仅依赖字面关键词。</p><p>当前未执行语义检索，不展示模拟结果。你可以先切换到关键词搜索。</p><el-button type="primary" @click="useKeywordSearch">用当前输入进行关键词搜索</el-button></section>
    <div v-else class="ps-search-summary" role="status" aria-live="polite">{{ loading ? '正在搜索…' : loadError ? '搜索失败，请重新加载' : `找到 ${total} 条与“${queryKeyword || '全部内容'}”相关的结果 · 当前页 ${filteredResults.length} 条` }}<p>当前条件：{{ filterSummary }}</p><small v-if="draftKeyword !== queryKeyword">输入内容尚未搜索，请点击“搜索”或按回车。</small></div>
    <el-alert
      v-if="searchMode !== 'semantic' && pageLimitExceeded"
      title="结果较多，最多展示前 100 页，请增加关键词或筛选条件。"
      type="warning"
      :closable="false"
      show-icon
    />

    <div v-if="searchMode !== 'semantic'" class="ps-search-layout">
      <aside class="ps-filter-panel">
        <h3><Filter />筛选条件</h3>
        <label><span>时间范围 <el-tooltip content="资讯按来源发布时间，内部资料和报告按更新时间，论文按平台发布时间过滤。" placement="top"><InfoFilled /></el-tooltip></span><el-select v-model="dateRange"><el-option label="全部时间" value="all" /><el-option label="近一周" value="week" /><el-option label="近一年" value="year" /></el-select></label>
        <label>内容来源<el-select v-model="source"><el-option label="全部来源" value="all" /><el-option label="公开来源" value="public" /><el-option label="内部资料" value="internal" /></el-select></label>
        <label>技术方向<el-checkbox-group v-model="directions" class="ps-check-list"><el-checkbox v-for="item in ['检测技术', '应力监测', '完整性管理', '腐蚀防护']" :key="item" :value="item">{{ item }}</el-checkbox></el-checkbox-group></label>
      </aside>

      <section v-loading="loading" :aria-busy="loading" class="ps-results-panel">
        <div class="ps-tabs-line" aria-label="按内容类型筛选">
          <button v-for="tab in tabs" :key="tab.value" type="button" :aria-pressed="activeType === tab.value" :class="{ 'is-active': activeType === tab.value }" @click="activeType = tab.value">{{ tab.label }} <span v-if="!loading && !loadError">{{ countByType(tab.value) }}</span></button>
        </div>
        <div v-if="filteredResults.length" class="ps-result-list">
          <article v-for="result in filteredResults" :key="`${result.type}-${result.id}`" class="ps-result-card">
            <div class="ps-result-type">{{ result.typeLabel }}</div>
            <div class="ps-result-body">
              <button type="button" class="ps-result-title" @click="openResult(result)">
                <template v-for="(part, index) in result.titleParts" :key="`title-${index}`"><mark v-if="part.match" class="ps-search-highlight">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template>
              </button>
              <p><template v-for="(part, index) in result.summaryParts" :key="`summary-${index}`"><mark v-if="part.match" class="ps-search-highlight">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template></p>
              <div class="ps-meta-row"><span>{{ result.meta }}</span><span v-for="tag in result.tags" :key="tag" class="ps-tag">{{ tag }}</span></div>
            </div>
            <div class="ps-result-actions"><el-tooltip :content="inBasket(result) ? '从资料篮移除，不删除原资料' : result.type === 'document' ? '请进入资料详情核验安全、解析和 AI 授权状态后选材' : '保存为科研编制选材'" placement="top"><span><el-button type="primary" plain :loading="busy(result)" :disabled="busy(result)" @click="add(result)">{{ inBasket(result) ? '取消加入资料篮' : result.type === 'document' ? '查看后选材' : '加入资料篮' }}</el-button></span></el-tooltip></div>
          </article>
        </div>
        <PortalEmptyState v-else-if="loadError && !loading" title="搜索失败" :description="loadError" action-label="重新加载" @action="reload" />
        <PortalEmptyState v-else-if="!loading" title="没有找到匹配结果" description="请减少筛选条件或尝试同义关键词。" action-label="清除筛选" @action="clearFilters" />
        <div v-if="total > 0 && !loading && !loadError" class="ps-pagination" aria-label="搜索结果分页">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="Math.min(total, pageSize * maxPageNum)"
            :pager-count="5"
            layout="total, sizes, ->, prev, pager, next, jumper"
            background
          />
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import { computed, ref, toRefs, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Filter, InfoFilled, Search } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { deletePipelineWorkspaceItem, savePipelineWorkspaceItem, searchPipelineIntelligence } from '@/api/pipeline/intelligence'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { openPortalContent } from '@/utils/portal/openContent'

const router = useRouter()
const portalStore = usePortalStore()
const maxPageNum = 100
const query = useListQuery({ q: '', mode: 'keyword', type: 'all', date: 'all', source: 'all', directions: [], page: 1, size: 10 }, { maxPage: maxPageNum })
const { q: queryKeyword, type: activeType, date: dateRange, source, directions, page: currentPage, size: pageSize } = toRefs(query)
const searchMode = computed({ get: () => query.mode === 'semantic' ? 'semantic' : 'keyword', set: value => { query.mode = value === 'semantic' ? 'semantic' : 'keyword' } })
const draftKeyword = ref(queryKeyword.value)
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
let pageCursors = {}
let cursorContext = ''
const tabs = [{ label: '全部', value: 'all' }, { label: '资讯', value: 'news' }, { label: '论文', value: 'paper' }, { label: '内部资料', value: 'document' }, { label: '我的报告', value: 'report' }]
const total = computed(() => Number(data.value?.total || 0))
const counts = computed(() => data.value?.counts || {})
const pageLimitExceeded = computed(() => total.value > pageSize.value * maxPageNum)

watch(queryKeyword, value => { draftKeyword.value = value })
function applyKeyword() {
  if (queryKeyword.value === draftKeyword.value) reload()
  else queryKeyword.value = draftKeyword.value
}
function useKeywordSearch() { queryKeyword.value = draftKeyword.value; searchMode.value = 'keyword' }
const { data, loading, loadError, reload } = useListRequest(() => ({
      keyword: queryKeyword.value || undefined,
      mode: searchMode.value,
      type: activeType.value,
      source: source.value,
      dateRange: dateRange.value,
      directions: directions.value.length ? directions.value.join(',') : undefined,
      pageNum: currentPage.value,
      pageSize: pageSize.value
}), params => {
  // This UI-only semantic state must never secretly call keyword search.
  if (params.mode === 'semantic') return Promise.resolve({ data: null })
  const { mode, ...requestParams } = params
  const context = JSON.stringify({ ...params, pageNum: undefined })
  if (context !== cursorContext) { cursorContext = context; pageCursors = {} }
  return searchPipelineIntelligence({ ...requestParams, cursor: pageCursors[params.pageNum - 1] || undefined })
})
const filteredResults = computed(() => (data.value?.rows || []).map(item => ({
      id: item.id,
      type: item.type,
      typeLabel: item.type_label,
      title: item.title,
      summary: item.summary,
      titleParts: item.title_parts || [{ text: item.title || '', match: false }],
      summaryParts: item.summary_parts || [{ text: item.summary || '', match: false }],
      meta: item.meta,
      tags: Array.isArray(item.tags) ? item.tags : [],
      sourceKind: item.source_kind,
      publishedAt: item.published_at,
      path: item.type === 'report' && ['daily', 'weekly', 'monthly'].includes(item.report_type)
        ? `/portal/digests/${item.id}`
        : item.path
    })))
watch(data, value => {
  if (!value) return
  if (value.nextCursor) pageCursors[currentPage.value] = value.nextCursor
  else delete pageCursors[currentPage.value]
  currentPage.value = validPage(total.value, pageSize.value, currentPage.value, maxPageNum)
})
const filterSummary = computed(() => [tabs.find(tab => tab.value === activeType.value)?.label, { all: '全部时间', week: '近一周', year: '近一年' }[dateRange.value], { all: '全部来源', public: '公开来源', internal: '内部资料' }[source.value], directions.value.join('、')].filter(Boolean).join(' / '))
function countByType(type) { return counts.value[type] ?? 0 }
function openResult(result) {
  if (!result?.path) return ElMessage.warning('该结果暂未提供可访问的详情路径')
  openPortalContent(router, result.path).catch(() => ElMessage.warning('该结果暂时无法打开，请刷新后重试'))
}
async function add(result) {
  if (result.type === 'document' && !inBasket(result)) return openResult(result)
  try {
    const outcome = await toggleBasket(result, result.type === 'news' ? 'article' : result.type)
    if (outcome === 'saved') ElMessage.success('已加入资料篮')
    else if (outcome === 'removed') ElMessage.success('已取消加入资料篮')
  } catch (error) { ElMessage.error(error?.msg || '资料篮更新失败，请重试') }
}
function clearFilters() {
  const unchanged = !queryKeyword.value && activeType.value === 'all' && dateRange.value === 'all' && source.value === 'all' && !directions.value.length && currentPage.value === 1
  activeType.value = 'all'; dateRange.value = 'all'; source.value = 'all'; directions.value = []; draftKeyword.value = ''; queryKeyword.value = ''; pageCursors = {}; currentPage.value = 1
  if (unchanged) reload()
}
</script>

<style scoped>
.ps-search-layout { grid-template-columns: 218px minmax(0, 1fr); }
@media (max-width: 960px) { .ps-search-layout { grid-template-columns: minmax(0, 1fr); } }
</style>
