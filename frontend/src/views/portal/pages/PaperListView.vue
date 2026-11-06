<template>
  <div class="ps-page ps-paper-library ps-list-page">
    <div class="ps-toolbar ps-paper-toolbar" role="search" aria-label="论文筛选">
      <div class="ps-paper-filter-row">
        <el-input v-model.trim="keyword" class="ps-paper-search" :prefix-icon="Search" clearable aria-label="搜索论文资料" placeholder="搜索题名、作者或摘要" @keydown.enter="reload" />
        <el-date-picker
          class="ps-paper-year"
          popper-class="ps-paper-year-popper"
          :model-value="selectedYearRange.length ? selectedYearRange : null"
          type="yearrange"
          value-format="YYYY"
          start-placeholder="起始年份"
          end-placeholder="结束年份"
          range-separator="至"
          clearable
          aria-label="论文发表年份范围"
          @update:model-value="changeYearRange"
        />
        <el-select v-model="classification" clearable filterable placeholder="全部类别" aria-label="论文类别">
          <el-option v-for="name in categoryOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select v-model="journal" clearable filterable placeholder="全部期刊 / 会议" aria-label="论文期刊或会议">
          <el-option v-for="item in journalOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-button v-if="hasActiveFilters" :icon="RefreshLeft" @click="resetFilters">重置筛选</el-button>
      </div>
    </div>
    <div class="ps-content-with-filter ps-list-stack">
      <section v-loading="loading" :aria-busy="loading" class="ps-list-stack">
        <div class="ps-paper-list ps-list-scroll" tabindex="0" aria-label="论文列表">
        <article v-for="paper in filteredPapers" :key="paper.id" class="ps-paper-card">
          <div class="ps-paper-card-top" aria-label="论文概览">
            <span class="ps-paper-source" aria-label="论文来源">{{ paper.journal }}</span>
            <time>{{ paper.publishedDate || paper.year || '日期未提供' }}</time>
          </div>
          <div class="ps-paper-main">
            <router-link class="ps-paper-title" :to="`/portal/papers/${paper.id}`">{{ paper.titleZh }}</router-link>
            <div v-if="paper.title && paper.title.trim() !== paper.titleZh?.trim()" class="ps-paper-en-title">{{ paper.title }}</div>
            <div class="ps-paper-byline"><span>作者：{{ paper.authors.join(' · ') }}</span><span v-if="paper.institutions.length">机构：{{ paper.institutions.join('；') }}</span></div>
            <p class="ps-paper-summary">{{ paper.abstract }}</p>
          </div>
          <div class="ps-paper-card-footer">
            <div class="ps-paper-topic-tags">
              <ContentEntities :entities="paper.entities" compact>
                <template #prepend><ContentCategory :name="contentCategory(paper)" /></template>
              </ContentEntities>
              <div v-if="paper.keywords.length" class="ps-paper-keywords" aria-label="论文关键词"><el-tag v-for="tag in paper.keywords" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag></div>
            </div>
            <div class="ps-paper-row-actions">
              <el-link v-if="doiUrl(paper)" class="ps-paper-doi" type="primary" underline="hover" :href="doiUrl(paper)" :title="`DOI: ${paper.doi}`" :aria-label="`查看论文原文，DOI: ${paper.doi}`" target="_blank" rel="noopener noreferrer">DOI 原文</el-link>
              <el-button type="primary" plain :loading="busy(paper)" :disabled="busy(paper)" @click="add(paper)">{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
            </div>
          </div>
          <div v-if="(paper.doi && !doiUrl(paper)) || collectionTime(paper) || paper.citationCount !== '未提供'" class="ps-paper-record-meta" aria-label="论文来源信息">
            <span v-if="paper.doi && !doiUrl(paper)" class="ps-paper-doi">DOI: {{ paper.doi }}</span>
            <span v-if="collectionTime(paper)">采集于 {{ collectionTime(paper) }}</span>
            <span v-if="paper.citationCount !== '未提供'">被引 {{ paper.citationCount }} 次</span>
          </div>
        </article>
        <PortalEmptyState v-if="loadError && !loading" title="论文加载失败" :description="loadError" action-label="重新加载" @action="reload" />
        <PortalEmptyState v-else-if="!filteredPapers.length && !loading" title="没有匹配的论文" description="尝试放宽关键词、年份、类别或期刊筛选。" :action-label="hasActiveFilters ? '重置筛选' : ''" @action="resetFilters" />
        </div>
        <div v-if="total > 0 && !loading && !loadError" class="ps-pagination" aria-label="论文列表分页">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
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
import ContentEntities from '../components/ContentEntities.vue'
import ContentCategory from '../components/ContentCategory.vue'
import { computed, toRefs, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshLeft, Search } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineContentFilters, listPipelineIntelligence, savePipelineWorkspaceItem, deletePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { normalizePortalPaper } from '@/store/modules/portal'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { cleanSummary } from '@/utils/portal/discovery'
import { contentCategory, collectionTime } from '@/utils/portal/contentPresentation'

const portalStore = usePortalStore()
const query = useListQuery({ q: '', year: 'all', years: [], journals: [], classification: '', page: 1, size: 10 })
const { q: keyword, year, years: yearRange, journals, classification, page: currentPage, size: pageSize } = toRefs(query)
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const facets = useListRequest(() => ({}), getPipelineContentFilters)
const categoryOptions = computed(() => [...new Set([...(facets.data.value?.paperCategories || facets.data.value?.categories || []), ...(classification.value ? [classification.value] : [])])])
const journalOptions = computed(() => [...new Set([...(facets.data.value?.journals || []), ...journals.value])])
// Keep older single-year links visible in the same range control.
const selectedYearRange = computed(() => year.value !== 'all' ? [String(year.value), String(year.value)] : yearRange.value || [])
const journal = computed({ get: () => journals.value[0] || '', set: value => { journals.value = value ? [value] : [] } })
const hasActiveFilters = computed(() => Boolean(keyword.value || selectedYearRange.value.length || classification.value || journal.value))
// The API accepts one journal keyword; normalize legacy multi-select URLs too.
watch(journals, values => { if (values.length > 1) journals.value = values.slice(0, 1) }, { immediate: true })
const { data, loading, loadError, reload } = useListRequest(() => {
  const [yearFrom, yearTo] = selectedYearRange.value.map(Number)
  return {
      category: 'paper',
      tag: classification.value || undefined,
      keyword: keyword.value || undefined,
      yearFrom,
      yearTo,
      journal: journal.value || undefined,
      pageNum: currentPage.value,
      pageSize: pageSize.value
  }
}, params => {
  if ([params.yearFrom, params.yearTo].some(value => value !== undefined && (!Number.isInteger(value) || value < 1600 || value > 2200))) throw new Error('请输入 1600–2200 之间的有效年份')
  if (params.yearFrom > params.yearTo) throw new Error('起始年份不能晚于结束年份')
  return listPipelineIntelligence(params)
})
const filteredPapers = computed(() => (data.value?.rows || []).map(item => ({
  ...normalizePortalPaper(item),
  authors: Array.isArray(item.authors) ? item.authors : item.authors ? [item.authors] : ['作者信息未提供'],
  institutions: item.institutions || [],
  journal: item.journal || item.source || item.source_name || '来源未提供',
  abstract: cleanSummary(item.abstractZh || item.abstract_zh || item.abstract || item.summary) || '摘要未提供，请进入详情核对来源。',
  citationCount: item.citations ?? item.citation_count ?? '未提供'
})))
const total = computed(() => Number(data.value?.total || 0))
watch(data, value => { if (value) currentPage.value = validPage(total.value, pageSize.value, currentPage.value) })
function changeYearRange(value) { year.value = 'all'; yearRange.value = value || [] }
function resetFilters() {
  const unchanged = !keyword.value && year.value === 'all' && !yearRange.value?.length && !journals.value.length && !classification.value && currentPage.value === 1
  keyword.value = ''; year.value = 'all'; yearRange.value = []; journals.value = []; classification.value = ''; currentPage.value = 1
  if (unchanged) reload()
}
async function add(paper) {
  try {
    const result = await toggleBasket(paper, 'paper')
    if (result === 'saved') ElMessage.success('已加入资料库')
    else if (result === 'removed') ElMessage.success('已取消加入资料库')
  } catch (error) { ElMessage.error(error?.msg || '资料库更新失败，请重试') }
}
function doiUrl(paper) {
  const doi = String(paper?.doi || '').trim().replace(/^doi:\s*/i, '').replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '')
  if (!/^10\.\d{4,9}\/\S+$/i.test(doi)) return ''
  return `https://doi.org/${doi.split('/').map(encodeURIComponent).join('/')}`
}
</script>

<style scoped>
.ps-paper-library > .ps-paper-toolbar { container-type: inline-size; }
.ps-paper-filter-row {
  display: grid;
  grid-template-columns: minmax(160px, 1.7fr) minmax(224px, 1.1fr) minmax(116px, .65fr) minmax(144px, .85fr) var(--paper-reset-track,);
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
  --el-component-size: 40px;
}
.ps-paper-filter-row:has(> .el-button) { --paper-reset-track: auto; }
.ps-paper-filter-row > :deep(:is(.el-input, .el-select, .el-date-editor)) { width: 100%; min-width: 0; box-sizing: border-box; }
.ps-paper-filter-row > .el-button { margin: 0; height: var(--el-component-size); }
.ps-paper-filter-row :deep(.ps-paper-year .el-range-input:focus-visible) { outline: none; }
.ps-paper-filter-row :deep(.ps-paper-year:has(.el-range-input:focus-visible)) {
  box-shadow: 0 0 0 1px var(--el-input-focus-border-color) inset;
}
:global(.ps-paper-year-popper .el-date-range-picker) { width: min(480px, calc(100vw - 24px)); }
:global(.ps-paper-year-popper .el-picker-panel__body) { display: flex; min-width: 0; }
:global(.ps-paper-year-popper .el-date-range-picker__content) { flex: 1; min-width: 0; padding: 12px 8px; }
:global(.ps-paper-year-popper .el-year-table td) { width: auto; padding-block: 2px; }
:global(.ps-paper-year-popper .el-year-table .el-date-table-cell__text) { width: min(100%, 44px); }
@container (max-width: 790px) {
  .ps-paper-filter-row { grid-template-columns: minmax(224px, 1.4fr) minmax(110px, 1fr) minmax(132px, 1fr) var(--paper-reset-track,); }
  .ps-paper-search { grid-column: 1 / -1; }
}
@container (max-width: 590px) {
  .ps-paper-filter-row { grid-template-columns: repeat(2, minmax(0, 1fr)); --el-component-size: 44px; }
  .ps-paper-filter-row > :deep(.ps-paper-year) { grid-column: 1 / -1; }
  .ps-paper-filter-row > .el-button { grid-column: 2; justify-self: end; }
}
/* Compact bibliographic header, reading content and a shared action footer. */
.ps-paper-library .ps-paper-list { gap: 10px; align-content: start; }
.ps-paper-library .ps-paper-card { display: block; min-width: 0; padding: 16px 20px; border-radius: 10px; box-shadow: none; }
.ps-paper-card-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; min-width: 0; margin-bottom: 8px; font-size: 13px; line-height: 1.5; color: var(--ps-muted); }
.ps-paper-card-top time { white-space: nowrap; }
.ps-paper-source { color: var(--ps-ink-2); font-weight: 600; overflow-wrap: anywhere; }
.ps-paper-main .ps-paper-title { display: block; margin: 0; color: var(--ps-ink); font-size: 18px; font-weight: 600; line-height: 1.55; text-align: left; overflow-wrap: anywhere; text-decoration: none; }
.ps-paper-main .ps-paper-title:hover { color: var(--ps-blue); }
.ps-paper-title:focus-visible, .ps-paper-doi:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 3px; border-radius: 4px; }
.ps-paper-main .ps-paper-en-title { margin: 4px 0 0; overflow-wrap: anywhere; }
.ps-paper-byline { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 5px; color: var(--ps-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-paper-main > .ps-paper-summary { display: block; margin: 9px 0 0; color: var(--ps-ink-2); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.ps-paper-card-footer { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-top: 12px; }
.ps-paper-topic-tags { flex: 1 1 260px; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.ps-paper-topic-tags :deep(.ps-content-entities) { margin: 0; max-width: 100%; }
.ps-paper-keywords { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.ps-paper-keywords .el-tag { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.ps-paper-row-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-left: auto; }
.ps-paper-row-actions > .el-button { margin: 0; }
.ps-paper-record-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 8px; color: var(--ps-muted); font-size: 12px; line-height: 1.6; }
.ps-paper-doi { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .ps-paper-library .ps-paper-card { padding: 14px; }
  .ps-paper-main .ps-paper-title { font-size: 16px; }
  .ps-paper-byline { flex-direction: column; gap: 4px; }
  .ps-paper-topic-tags { flex-basis: 100%; }
  .ps-paper-row-actions { width: 100%; justify-content: flex-end; }
  .ps-paper-row-actions > .el-button { min-height: 44px; }
}
</style>
