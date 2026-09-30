<template>
  <div class="ps-page ps-reading-page">
    <div class="ps-breadcrumb"><button type="button" @click="router.push('/portal')">首页</button><span>/</span><button type="button" @click="router.push('/portal/papers')">论文资料</button><span>/</span><b>论文详情</b></div>
    <PortalEmptyState v-if="!paper" title="论文不存在" description="该论文记录可能已移除，或当前账号没有访问权限。" action-label="返回论文资料" @action="router.push('/portal/papers')" />
    <template v-else>
    <section class="ps-paper-detail-hero">
      <div class="ps-paper-access" :class="`is-${accessClass(paper.access)}`">{{ paper.access }}</div>
      <h1>{{ paper.titleZh }}</h1><p class="ps-paper-original-title">{{ paper.title }}</p>
      <div class="ps-author-map"><div v-for="(author, index) in paper.authors" :key="author"><span>{{ author }}</span><small>{{ paper.institutions[index] || paper.institutions[0] }}</small></div></div>
      <div class="ps-paper-detail-meta"><span>{{ paper.journal }}</span><span>{{ paper.year }}</span><span>DOI {{ paper.doi }}</span><span>被引 {{ paper.citations }} 次</span></div>
      <div class="ps-article-actions">
        <el-button type="primary" @click="add"><Collection />加入资料篮</el-button>
        <el-button @click="startResearch"><MagicStick />用于科研报告</el-button>
        <el-button @click="copyCitation"><DocumentCopy />复制引用</el-button>
        <el-tooltip :content="paperUrl ? '在新窗口打开可信来源' : '当前记录未提供可访问链接'" placement="top">
          <span class="ps-disabled-action-wrap">
            <el-button :disabled="!paperUrl" @click="openPaperSource"><TopRight />{{ paper.fullTextUrl || paper.full_text_url || paper.documentUrl || paper.document_url ? '查看全文' : '查看来源' }}</el-button>
          </span>
        </el-tooltip>
      </div>
    </section>
    <div class="ps-reading-layout">
      <article class="ps-paper-detail-body">
        <nav class="ps-tabs-line"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></nav>
        <section v-if="activeTab === '摘要'" class="ps-paper-section"><h2>摘要</h2><p>{{ paper.abstract }}</p><h3>关键词</h3><div class="ps-tag-row"><span v-for="tag in paper.keywords" :key="tag" class="ps-tag">{{ tag }}</span></div><div class="ps-evidence-note"><Warning />当前全文状态为“{{ paper.access }}”。平台仅在授权范围内展示和处理全文内容。</div></section>
        <section v-else-if="activeTab === 'AI解读'" class="ps-paper-section"><h2>AI 解读</h2><div class="ps-insight-list"><article><span>01</span><div><strong>研究问题</strong><p>解决多源检测条件下缺陷识别结果不一致、工程解释困难的问题。</p></div></article><article><span>02</span><div><strong>方法贡献</strong><p>建立统一评价框架，比较不同模型的数据需求、泛化能力和可解释性。</p></div></article><article><span>03</span><div><strong>项目价值</strong><p>可用于技术路线选型、指标设计和工程验证方案编制。</p></div></article></div></section>
        <section v-else class="ps-paper-section"><h2>{{ activeTab }}</h2><p>该部分将在接入正式论文元数据与授权全文后展示完整内容。</p></section>
      </article>
      <aside class="ps-reading-aside"><section class="ps-panel"><h3>关联科技资讯</h3><button v-for="item in newsItems.slice(0, 3)" :key="item.id" type="button" class="ps-related-item" @click="router.push(`/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}</small></button></section><section class="ps-panel"><h3>相似论文</h3><button v-for="item in relatedPapers" :key="item.id" type="button" class="ps-related-item" @click="router.push(`/portal/papers/${item.id}`)"><strong>{{ item.titleZh }}</strong><small>{{ item.journal }} · {{ item.year }}</small></button></section></aside>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Collection, DocumentCopy, MagicStick, TopRight, Warning } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import PortalEmptyState from '../components/PortalEmptyState.vue'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const activeTab = ref('摘要')
const tabs = ['摘要', 'AI解读', '引用信息', '关联资料']
const paper = computed(() => portalStore.paperItems.find(item => item.id === route.params.itemId) || null)
const paperUrl = computed(() => {
  const directUrl = paper.value?.fullTextUrl || paper.value?.full_text_url || paper.value?.documentUrl || paper.value?.document_url || paper.value?.sourceUrl || paper.value?.source_url || paper.value?.url || paper.value?.link
  if (directUrl) return directUrl
  return paper.value?.doi && paper.value.doi !== '待补充' ? `https://doi.org/${String(paper.value.doi).trim()}` : ''
})
const relatedPapers = computed(() => portalStore.paperItems.filter(item => item.id !== paper.value?.id).slice(0, 3))
const newsItems = computed(() => portalStore.newsItems)
function add() { ElMessage.success(portalStore.addToBasket({ ...paper.value, title: paper.value.titleZh, type: '论文' }) ? '已加入资料篮' : '资料已在资料篮中') }
function accessClass(value) { return ({ '开放获取': 'open', '用户上传': 'upload', '仅元数据': 'meta', '访问受限': 'restricted' })[value] }
function citationText() {
  const authors = (paper.value.authors || []).join(', ') || '作者信息待补充'
  const title = paper.value.title || paper.value.titleZh || '题名待补充'
  const journal = paper.value.journal || '来源待补充'
  const doi = paper.value.doi && paper.value.doi !== '待补充' ? ` DOI: ${paper.value.doi}.` : ''
  return `${authors}. ${title}[J]. ${journal}, ${paper.value.year || '年份待补充'}.${doi}`
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
async function copyCitation() {
  try {
    await writeClipboard(citationText())
    ElMessage.success('引用信息已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动选择 DOI 与引用信息')
  }
}
function openPaperSource() {
  if (!paperUrl.value) return
  try {
    const target = new URL(paperUrl.value, window.location.origin)
    if (!['http:', 'https:'].includes(target.protocol)) throw new Error('unsupported protocol')
    window.open(target.href, '_blank', 'noopener,noreferrer')
  } catch (error) {
    ElMessage.error('来源链接无效，暂时无法打开')
  }
}
function startResearch() {
  portalStore.addToBasket({ ...paper.value, title: paper.value.titleZh, type: '论文' })
  router.push({ path: '/portal/research/create', query: { source: paper.value.id } })
}
</script>
