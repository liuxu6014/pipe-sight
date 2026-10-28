<template>
  <div class="ps-page ps-home-page ps-home-dashboard ps-home-viewport">
    <section class="ps-home-search-panel" aria-label="首页资料检索">
      <form class="ps-home-search" role="search" @submit.prevent="submitSearch">
        <Search aria-hidden="true" />
        <input v-model.trim="keyword" maxlength="200" aria-label="搜索研究资料" placeholder="搜索资讯、论文、研究资料或我的报告" />
        <el-button v-if="keyword" class="ps-ui-action ps-home-search-clear" aria-label="清空搜索" @click="clearSearch"><Close /></el-button>
        <el-button native-type="submit" type="primary" :disabled="!keyword">搜索</el-button>
      </form>
    </section>

    <section v-if="submittedKeyword" class="ps-panel ps-home-search-results" aria-label="首页搜索结果" :aria-busy="searchRequest.loading.value">
      <div class="ps-section-head"><h2>搜索结果</h2><el-button plain @click="clearSearch">收起结果</el-button></div>
      <p class="ps-home-result-status" role="status">{{ searchRequest.loading.value ? '正在搜索…' : searchRequest.loadError.value ? '搜索失败' : `“${submittedKeyword}” · 共 ${searchTotal} 条结果` }}</p>
      <div class="ps-home-panel-content" tabindex="0" aria-label="首页搜索结果滚动区">
      <el-skeleton v-if="searchRequest.loading.value" :rows="4" animated />
      <PortalEmptyState v-else-if="searchRequest.loadError.value" compact title="搜索失败" :description="searchRequest.loadError.value" action-label="重试" @action="searchRequest.reload" />
      <ul v-else-if="searchResults.length" class="ps-home-result-list">
        <li v-for="item in searchResults" :key="`${item.type}-${item.id}`">
          <span class="ps-home-content-type">{{ item.type_label || typeLabels[item.type] || '资料' }}</span>
          <div><button type="button" class="ps-home-item-title" :disabled="!resultPath(item)" @click="openPortalContent(router, resultPath(item))">{{ item.title }}</button><p>{{ cleanSummary(item.summary) || '摘要未提供' }}</p><small>{{ cleanResultMeta(item.meta) }}</small></div>
        </li>
      </ul>
      <PortalEmptyState v-else compact title="没有匹配结果" description="请缩短关键词或尝试其他技术名称。" />
      </div>
      <div v-if="searchTotal > 0 && !searchRequest.loading.value && !searchRequest.loadError.value" class="ps-pagination" aria-label="首页搜索结果分页"><el-pagination v-model:current-page="searchPage" v-model:page-size="searchPageSize" :page-sizes="[10, 20, 50]" :total="Math.min(searchTotal, searchPageSize * 100)" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
    </section>

    <section class="ps-home-statistics" aria-label="可访问数据统计" :aria-busy="overview.loading.value">
      <div v-for="metric in metrics" :key="metric.key" class="ps-home-metric"><span class="ps-home-metric-label">{{ metric.label }}</span><div class="ps-home-metric-number"><strong class="ps-home-metric-value">{{ metric.value === null ? '—' : metric.value.toLocaleString() }}</strong><small v-if="metric.added !== null" class="ps-home-metric-added" :class="{ 'is-positive': metric.added > 0 }" :aria-label="`今日新增 ${metric.added} ${metric.unit}`" :title="`今日新增 ${metric.added} ${metric.unit}`">+{{ metric.added.toLocaleString() }}</small><small class="ps-home-metric-unit">{{ metric.unit }}</small></div></div>
    </section>
    <p v-if="overview.loadError.value" class="ps-home-load-warning" role="alert">统计加载失败，不以零代替。<el-button plain @click="overview.reload">重试</el-button></p>

    <section class="ps-home-modules" aria-label="四大功能">
      <button v-for="entry in modules" :key="entry.path" type="button" class="ps-home-module" @click="router.push(entry.path)">
        <span class="ps-home-module-icon"><component :is="entry.icon" /></span>
        <strong>{{ entry.title }}</strong><p>{{ entry.description }}</p><span class="ps-home-module-link">{{ entry.action }}<ArrowRight /></span>
      </button>
    </section>

    <section class="ps-panel ps-home-latest" aria-label="最新资讯与论文">
      <div class="ps-section-head"><h2>最新资讯与论文</h2><div class="ps-home-feed-tabs" role="group" aria-label="最新内容类型"><button v-for="tab in feedTabs" :key="tab.key" type="button" :aria-pressed="feedType === tab.key" @click="feedType = tab.key">{{ tab.label }}</button></div></div>
      <p v-if="articles.loadError.value || papers.loadError.value" class="ps-home-load-warning" role="alert">{{ articles.loadError.value ? '资讯加载失败。' : '' }}{{ papers.loadError.value ? '论文加载失败。' : '' }}<el-button plain @click="reloadLatest">重试</el-button></p>
      <div class="ps-home-panel-content" tabindex="0" aria-label="最新资讯与论文滚动区">
      <el-skeleton v-if="articles.loading.value || papers.loading.value" :rows="6" animated />
      <ul v-else-if="latestItems.length" class="ps-home-latest-list">
        <li v-for="item in latestItems" :key="`${item.kind}-${item.id}`">
          <button type="button" class="ps-home-latest-item" @click="openPortalContent(router, item.path)">
            <img v-if="item.cover_image" :src="item.cover_image" alt="文章配图" loading="lazy" />
            <span class="ps-home-latest-copy"><span class="ps-home-item-meta"><b>{{ item.kindLabel }}</b><time>{{ item.date }}</time></span><strong>{{ item.title }}</strong><span class="ps-home-item-summary">{{ item.summary || '摘要未提供，可进入详情阅读。' }}</span><small>{{ item.source || '来源未提供' }}</small></span><ArrowRight class="ps-home-latest-arrow" />
          </button>
        </li>
      </ul>
      <PortalEmptyState v-else compact title="暂无可访问内容" description="仅展示已发布且当前账号允许阅读的内容。" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Close, Collection, Document, DocumentAdd, Reading, Search } from '@element-plus/icons-vue'
import { getPipelinePortalOverview, listPipelineIntelligence, searchPipelineIntelligence } from '@/api/pipeline/intelligence'
import { useListRequest, validPage } from '@/utils/portal/listQuery'
import { cleanSummary, cleanResultMeta, combineLatest, resultPath } from '@/utils/portal/discovery'
import { openPortalContent } from '@/utils/portal/openContent'
import PortalEmptyState from '../components/PortalEmptyState.vue'

const router = useRouter()
const keyword = ref('')
const submittedKeyword = ref('')
const searchPage = ref(1)
const searchPageSize = ref(10)
watch(searchPageSize, () => { searchPage.value = 1 })
const feedType = ref('all')
const typeLabels = { news: '资讯', paper: '论文', document: '内部资料', report: '报告' }
const overview = useListRequest(() => ({}), getPipelinePortalOverview)
const articles = useListRequest(() => ({ category: 'article', sortBy: 'publication', pageNum: 1, pageSize: 8 }), listPipelineIntelligence)
const papers = useListRequest(() => ({ category: 'paper', sortBy: 'publication', pageNum: 1, pageSize: 8 }), listPipelineIntelligence)
const searchRequest = useListRequest(() => ({ keyword: submittedKeyword.value, pageNum: searchPage.value, pageSize: searchPageSize.value, type: 'all', source: 'all', dateRange: 'all' }), params => params.keyword ? searchPipelineIntelligence(params) : Promise.resolve({ data: null }))
const searchResults = computed(() => searchRequest.data.value?.rows || [])
const searchTotal = computed(() => Number(searchRequest.data.value?.total || 0))
watch(searchRequest.data, value => { if (value) searchPage.value = validPage(searchTotal.value, searchPageSize.value, searchPage.value, 100) })
const metrics = computed(() => [
  { key: 'paperCount', label: '论文总数', unit: '篇', addedKey: 'todayPaperCount' },
  { key: 'newsCount', label: '新闻数量', unit: '篇', addedKey: 'todayNewsCount' },
  { key: 'wechatCount', label: '公众号数量', unit: '篇', addedKey: 'todayWechatCount' },
  { key: 'todayAddedCount', label: '今日新增', unit: '条' },
  { key: 'reportCount', label: '报告生成数', unit: '份' }
].map(metric => {
  const available = !overview.loading.value && !overview.loadError.value
  return { ...metric,
    value: available && Number.isFinite(overview.data.value?.[metric.key]) ? overview.data.value[metric.key] : null,
    added: available && metric.addedKey && Number.isFinite(overview.data.value?.[metric.addedKey]) ? overview.data.value[metric.addedKey] : null }
}))
const modules = [
  { title: '新闻资讯', description: '浏览行业动态、技术进展与公众号文章', path: '/portal/news', action: '浏览资讯', icon: Collection },
  { title: '科研论文', description: '检索管网研究论文与可访问文献', path: '/portal/papers', action: '检索论文', icon: Document },
  { title: '科研报告', description: '选择模板与研究资料，开始编制报告', path: '/portal/research/create', action: '创建报告', icon: DocumentAdd },
  { title: '情报简报', description: '确定覆盖周期与选题，汇总情报动态', path: '/portal/digests/create', action: '生成简报', icon: Reading }
]
const feedTabs = [{ key: 'all', label: '全部' }, { key: 'news', label: '资讯' }, { key: 'paper', label: '论文' }]
const latestItems = computed(() => combineLatest(articles.data.value?.rows || [], papers.data.value?.rows || []).filter(item => feedType.value === 'all' || item.kind === feedType.value).slice(0, 8))
function submitSearch() {
  if (!keyword.value.trim()) return
  if (submittedKeyword.value === keyword.value && searchPage.value === 1) searchRequest.reload()
  else { searchPage.value = 1; submittedKeyword.value = keyword.value }
}
function clearSearch() { keyword.value = ''; submittedKeyword.value = ''; searchPage.value = 1 }
function reloadLatest() { articles.reload(); papers.reload() }
</script>

<style scoped lang="scss">
.ps-home-page.ps-home-dashboard { display: block; height: auto; min-height: calc(100dvh - 70px); }
.ps-home-dashboard > section + section { margin-top: 16px; }
.ps-home-search-panel { display: block; padding: 20px 24px 16px; border: 1px solid #dce8ef; border-radius: 12px; background: #edf5fa; }
.ps-home-search { display: flex; align-items: center; gap: 12px; max-width: 1000px; margin: auto; padding: 5px 5px 5px 18px; border: 1px solid #b8cfdf; border-radius: 9px; background: #fff; }
.ps-home-search > svg { width: 21px; height: 21px; flex-shrink: 0; color: var(--ps-muted); }
.ps-home-search input { flex: 1; width: 0; min-width: 0; height: 42px; border: 0; background: transparent; font: inherit; font-size: 15px; color: var(--ps-ink); }
.ps-home-search input:focus-visible { outline: none; }
.ps-home-search:has(button:focus-visible) { box-shadow: none; }
.ps-home-search .el-button { height: 44px; min-width: 92px; margin: 0; }
.ps-home-search-clear { width: 32px; height: 32px; display: grid; place-items: center; padding: 6px; border: 0; border-radius: 5px; background: transparent; color: var(--ps-muted); }
.ps-home-search-clear:hover { background: var(--ps-blue-soft); }
.ps-home-statistics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); background: #fff; border: 1px solid var(--ps-line); border-radius: 12px; padding: 18px 0; }
.ps-home-statistics > div { min-width: 0; padding: 0 16px; display: flex; flex-direction: column; align-items: flex-start; justify-content: flex-end; gap: 10px; }
.ps-home-statistics > div + div { border-left: 1px solid var(--ps-line); }
.ps-home-metric-label { color: var(--ps-ink-2); font-size: 14px; font-weight: 500; line-height: 1.5; }
.ps-home-metric-number { display: grid; grid-template-columns: auto auto; grid-template-areas: "value added" "value unit"; align-items: end; min-height: 52px; column-gap: 6px; }
.ps-home-metric-added { grid-area: added; align-self: start; color: var(--ps-muted); font-size: 12px; line-height: 16px; font-variant-numeric: tabular-nums; }
.ps-home-metric-added.is-positive { color: var(--ps-green); }
.ps-home-metric-value { grid-area: value; min-width: 0; color: var(--ps-blue); font-size: 44px; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.ps-home-metric-unit { grid-area: unit; padding-bottom: 4px; color: var(--ps-muted); font-size: 12px; font-weight: 400; }
.ps-home-modules { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.ps-home-module { display: flex; flex-direction: column; align-items: flex-start; min-width: 0; padding: 22px; border: 1px solid var(--ps-line); border-radius: 12px; background: #fff; text-align: left; color: var(--ps-ink); }
.ps-home-module:hover { border-color: #89afc8; background: #f8fbfd; }
.ps-home-module-icon { display: grid; place-items: center; width: 42px; height: 42px; margin-bottom: 14px; border-radius: 10px; background: var(--ps-blue-soft); color: var(--ps-blue); }
.ps-home-module-icon svg { width: 23px; height: 23px; }
.ps-home-module > strong { font-size: 19px; font-weight: 600; }
.ps-home-module p { margin: 10px 0 18px; color: var(--ps-muted); font-size: 13px; line-height: 1.7; }
.ps-home-module-link { display: flex; align-items: center; gap: 6px; margin-top: auto; color: var(--ps-blue); font-size: 13px; }
.ps-home-module-link svg { width: 14px; }
.ps-home-latest, .ps-home-search-results { padding: 22px; }
.ps-home-dashboard h2 { margin: 0; font-size: 19px; font-weight: 600; }
.ps-home-feed-tabs { display: flex; flex-wrap: wrap; gap: 4px; }
.ps-home-feed-tabs button { padding: 7px 14px; min-height: 36px; border: 0; border-radius: 6px; background: transparent; font: inherit; font-size: 13px; color: var(--ps-muted); }
.ps-home-feed-tabs button[aria-pressed="true"] { color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-home-latest-list, .ps-home-result-list { list-style: none; margin: 0; padding: 0; }
.ps-home-latest-list li + li, .ps-home-result-list li + li { border-top: 1px solid var(--ps-line-soft); }
.ps-home-latest-item { display: flex; align-items: center; gap: 18px; width: 100%; padding: 20px 0; border: 0; border-radius: 6px; background: transparent; text-align: left; font: inherit; }
.ps-home-latest-item:hover { background: #f8fbfd; }
.ps-home-latest-item img { flex: 0 0 160px; width: 160px; height: 104px; object-fit: cover; border-radius: 8px; }
.ps-home-latest-copy { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 0; }
.ps-home-item-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--ps-muted); }
.ps-home-item-meta b, .ps-home-content-type { color: var(--ps-blue); background: var(--ps-blue-soft); padding: 3px 7px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.ps-home-latest-copy > strong { font-size: 16px; color: var(--ps-ink); line-height: 1.6; font-weight: 600; overflow-wrap: anywhere; }
.ps-home-item-summary, .ps-home-result-list p { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; color: var(--ps-muted); font-size: 13px; line-height: 1.8; }
.ps-home-latest-copy small, .ps-home-result-list small { color: var(--ps-muted); font-size: 12px; }
.ps-home-latest-arrow { width: 16px; flex-shrink: 0; color: var(--ps-muted); }
.ps-home-load-warning, .ps-home-result-status { color: var(--ps-muted); font-size: 13px; line-height: 1.7; }
.ps-home-result-list li { display: flex; align-items: flex-start; gap: 16px; padding: 16px 0; }
.ps-home-result-list li > div { min-width: 0; flex: 1; }
.ps-home-content-type { flex-shrink: 0; }
.ps-home-item-title { border: 0; border-radius: 4px; padding: 0; background: transparent; text-align: left; color: var(--ps-ink); font: inherit; font-size: 16px; font-weight: 600; line-height: 1.6; }
.ps-home-item-title:hover { color: var(--ps-blue); }
@media (max-width: 900px) {
  .ps-home-modules { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ps-home-statistics > div { padding: 2px 16px; column-gap: 8px; }
}
@media (max-width: 600px) {
  .ps-home-search-panel { padding: 18px 12px 14px; }
  .ps-home-search { gap: 8px; padding-left: 10px; }
  .ps-home-search input { font-size: 14px; }
  .ps-home-search .el-button { min-width: 62px; padding-inline: 12px; }
  .ps-home-statistics { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 16px; padding-block: 16px; }
  .ps-home-statistics > div { gap: 6px; }
  .ps-home-metric-value { font-size: 36px; }
  .ps-home-statistics > div:nth-child(odd) { border-left: 0; }
  .ps-home-statistics > div:last-child { grid-column: 1 / -1; border-top: 1px solid var(--ps-line); padding-top: 14px; flex-direction: row; align-items: center; justify-content: space-between; }
  .ps-home-statistics > div:last-child .ps-home-metric-number { min-height: 0; }
  .ps-home-modules { gap: 12px; }
  .ps-home-module { padding: 16px; }
  .ps-home-module > strong { font-size: 17px; }
  .ps-home-latest, .ps-home-search-results { padding: 16px; }
  .ps-home-latest-item { flex-wrap: wrap; gap: 12px; }
  .ps-home-latest-item img { flex: 0 0 100%; width: 100%; height: 150px; }
  .ps-home-latest-arrow { display: none; }
  .ps-home-latest .ps-section-head { align-items: flex-start; flex-wrap: wrap; gap: 10px; }
}
</style>
