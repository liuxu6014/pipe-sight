<template>
  <div class="ps-page">
    <PortalPageHeader title="论文资料" />
    <div class="ps-toolbar ps-paper-toolbar"><div class="ps-search-inline"><Search /><input v-model.trim="keyword" placeholder="搜索题名、作者、机构或 DOI" /></div><el-select v-model="year" style="width: 130px"><el-option label="全部年份" value="all" /><el-option label="2026" value="2026" /><el-option label="2025" value="2025" /><el-option label="2024" value="2024" /></el-select><el-select v-model="access" style="width: 150px"><el-option label="全部全文状态" value="all" /><el-option v-for="item in accessOptions" :key="item" :label="item" :value="item" /></el-select></div>
    <div class="ps-content-with-filter">
      <aside class="ps-filter-panel"><h3><Filter />筛选论文</h3><label>年份范围<el-slider v-model="yearRange" range :min="2020" :max="2026" /></label><label>期刊 / 会议<el-checkbox-group v-model="journals"><el-checkbox v-for="item in journalOptions" :key="item" :value="item">{{ item }}</el-checkbox></el-checkbox-group></label><label>关键词<div class="ps-keyword-cloud"><button v-for="word in ['缺陷识别', '应力监测', '数据融合', '数字孪生']" :key="word" type="button" @click="keyword = word">{{ word }}</button></div></label></aside>
      <section class="ps-paper-list">
        <div class="ps-list-summary">共 {{ filteredPapers.length }} 篇论文 · 按相关性排序</div>
        <article v-for="paper in filteredPapers" :key="paper.id" class="ps-paper-card">
          <div class="ps-paper-access" :class="`is-${accessClass(paper.access)}`">{{ paper.access }}</div>
          <div class="ps-paper-main">
            <button type="button" class="ps-paper-title" @click="router.push(`/portal/papers/${paper.id}`)">{{ paper.titleZh }}</button>
            <div class="ps-paper-en-title">{{ paper.title }}</div>
            <div class="ps-paper-authors">{{ paper.authors.join(' · ') }}<span>{{ paper.institutions.join('；') }}</span></div>
            <p>{{ paper.abstract }}</p>
            <div class="ps-tag-row"><span v-for="tag in paper.keywords" :key="tag" class="ps-tag">{{ tag }}</span></div>
          </div>
          <aside class="ps-paper-meta" aria-label="论文概览">
            <h3>文献概览</h3>
            <div><span>来源期刊</span><strong>{{ paper.journal }}</strong></div>
            <div><span>发表年份</span><strong>{{ paper.year }}</strong></div>
            <div><span>被引次数</span><strong>{{ paper.citations || 0 }}</strong></div>
            <div><span>DOI</span><strong>{{ paper.doi || '待补充' }}</strong></div>
          </aside>
          <div class="ps-paper-actions">
            <el-button type="primary" text @click="router.push(`/portal/papers/${paper.id}`)">查看详情</el-button>
            <el-button @click="add(paper)">加入资料篮</el-button>
            <el-button @click="copyCitation(paper)">复制引用</el-button>
            <el-tooltip :content="paperUrl(paper) ? '在新窗口打开可信来源' : '当前记录未提供可访问链接'" placement="top">
              <span class="ps-disabled-action-wrap">
                <el-button text :disabled="!paperUrl(paper)" @click="openPaperSource(paper)">{{ sourceActionLabel(paper) }}</el-button>
              </span>
            </el-tooltip>
          </div>
        </article>
        <PortalEmptyState v-if="!filteredPapers.length" title="没有匹配的论文" description="尝试放宽年份、期刊或全文状态筛选。" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Filter, Search } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'

const router = useRouter()
const portalStore = usePortalStore()
const keyword = ref('')
const year = ref('all')
const access = ref('all')
const yearRange = ref([2020, 2026])
const journals = ref([])
const paperItems = computed(() => portalStore.paperItems)
const accessOptions = ['开放获取', '用户上传', '仅元数据', '访问受限']
const journalOptions = ['JPSE', 'NDT & E', 'RESS', 'Applied Energy']
const filteredPapers = computed(() => paperItems.value.filter(item => (year.value === 'all' || String(item.year) === year.value) && (access.value === 'all' || item.access === access.value) && item.year >= yearRange.value[0] && item.year <= yearRange.value[1] && (!keyword.value || `${item.title}${item.titleZh}${(item.authors || []).join('')}${(item.institutions || []).join('')}${item.doi}${(item.keywords || []).join('')}`.toLowerCase().includes(keyword.value.toLowerCase()))))
function add(paper) { ElMessage.success(portalStore.addToBasket({ ...paper, title: paper.titleZh, type: '论文' }) ? '已加入资料篮' : '资料已在资料篮中') }
function accessClass(value) { return ({ '开放获取': 'open', '用户上传': 'upload', '仅元数据': 'meta', '访问受限': 'restricted' })[value] }
function paperUrl(paper) {
  const directUrl = paper?.fullTextUrl || paper?.full_text_url || paper?.documentUrl || paper?.document_url || paper?.sourceUrl || paper?.source_url || paper?.url || paper?.link
  if (directUrl) return directUrl
  return paper?.doi && paper.doi !== '待补充' ? `https://doi.org/${String(paper.doi).trim()}` : ''
}
function sourceActionLabel(paper) { return paper?.fullTextUrl || paper?.full_text_url || paper?.documentUrl || paper?.document_url ? '查看全文' : '查看来源' }
function citationText(paper) {
  const authors = (paper.authors || []).join(', ') || '作者信息待补充'
  const title = paper.title || paper.titleZh || '题名待补充'
  const journal = paper.journal || '来源待补充'
  const doi = paper.doi && paper.doi !== '待补充' ? ` DOI: ${paper.doi}.` : ''
  return `${authors}. ${title}[J]. ${journal}, ${paper.year || '年份待补充'}.${doi}`
}
async function writeClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch (error) {
      // Some embedded browsers expose Clipboard API but deny it; use the selection fallback below.
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('copy failed')
}
async function copyCitation(paper) {
  try {
    await writeClipboard(citationText(paper))
    ElMessage.success('引用信息已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请在详情页手动选择引用信息')
  }
}
function openPaperSource(paper) {
  const url = paperUrl(paper)
  if (!url) return
  try {
    const target = new URL(url, window.location.origin)
    if (!['http:', 'https:'].includes(target.protocol)) throw new Error('unsupported protocol')
    window.open(target.href, '_blank', 'noopener,noreferrer')
  } catch (error) {
    ElMessage.error('来源链接无效，暂时无法打开')
  }
}
</script>
