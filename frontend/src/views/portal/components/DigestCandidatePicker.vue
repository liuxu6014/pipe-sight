<template>
  <section class="ps-digest-candidate-picker" aria-label="全量候选资讯" :aria-busy="loading">
    <p v-if="readOnly" class="ps-candidate-note">当前为只读模式，不能添加来源；已关联资料可在来源清单查看。</p>
    <template v-else>
      <form class="ps-candidate-filters" @submit.prevent="search.search">
        <el-input v-model="query.keyword" maxlength="200" clearable placeholder="检索全部资讯，回车搜索" aria-label="候选资讯关键词" @clear="search.search" />
        <div><el-select v-model="query.source" aria-label="候选资讯来源类型" placeholder="全部来源" @change="search.search"><el-option label="全部来源" value="" /><el-option label="新闻网站" value="news" /><el-option label="微信公众号" value="wechat" /></el-select><el-button native-type="submit" :loading="loading">搜索</el-button></div>
        <small>添加来源不会自动改写正文，翻页不会移除已添加资料。</small>
      </form>
      <div class="ps-candidate-results">
        <div v-if="error" class="ps-candidate-error" role="alert"><p>{{ error }}</p><el-button plain type="primary" @click="search.reload">重新加载</el-button></div>
        <p v-else-if="loading" class="ps-candidate-note" role="status">正在检索全部资讯…</p>
        <ul v-else-if="rows.length" class="ps-candidate-result-list">
          <li v-for="item in rows" :key="item.id">
            <router-link :to="`/portal/news/${item.id}`">{{ item.title || '未命名资讯' }}</router-link>
            <p v-if="item.summary" class="ps-candidate-excerpt">{{ item.summary }}</p>
            <small>{{ candidateSourceLabel(item) }}</small>
            <time>{{ formatBusinessTime(item.publish_time || item.publishTime || item.published_at || item.time) || '发布时间未提供' }}</time>
            <el-button plain type="primary" :disabled="isSelected(item.id)" :aria-label="`${isSelected(item.id) ? '当前栏目已添加' : '添加来源'}：${item.title}`" @click="select(item)">{{ isSelected(item.id) ? '当前栏目已添加' : '添加来源' }}</el-button>
          </li>
        </ul>
        <p v-else class="ps-candidate-note">没有匹配的资讯，请调整关键词或来源条件。</p>
      </div>
      <footer class="ps-candidate-pagination">
        <div><span>{{ error ? '总数暂不可用' : loading ? '正在检索…' : `共 ${total} 条` }}</span><el-select :model-value="query.size" aria-label="每页候选资讯条数" :disabled="loading" @change="search.setSize"><el-option v-for="size in [10, 20, 50]" :key="size" :value="size" :label="`${size}条/页`" /></el-select></div>
        <el-pagination :current-page="query.page" :page-size="query.size" :total="total" :pager-count="5" layout="prev, pager, next" :disabled="loading || Boolean(error)" small background @current-change="changePage" />
      </footer>
    </template>
  </section>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue'
import { listPipelineIntelligence } from '@/api/pipeline/intelligence'
import { createDigestCandidateSearch, candidateSourceLabel } from '@/utils/portal/digestCandidates'
import { formatBusinessTime } from '@/utils/portal/businessTime'
import usePortalStore from '@/store/modules/portal'

const props = defineProps({ selectedIds: { type: Array, default: () => [] }, readOnly: Boolean, enabled: { type: Boolean, default: true } })
const emit = defineEmits(['select'])
const store = usePortalStore()
const search = createDigestCandidateSearch(listPipelineIntelligence)
const { query, rows, total, loading, error } = search
const isSelected = id => props.selectedIds.some(value => String(value) === String(id))
function changePage(value) { if (!loading.value && !error.value) return search.setPage(value) }
function select(item) {
  if (props.readOnly || !props.enabled || loading.value || error.value || isSelected(item.id)) return
  const current = rows.value.find(row => row.id === item.id)
  if (current) emit('select', current)
}
watch(() => [props.enabled, props.readOnly, store.workspaceEpoch], () => search.configure({ enabled: props.enabled && !props.readOnly, epoch: store.workspaceEpoch }), { immediate: true, flush: 'sync' })
onBeforeUnmount(search.dispose)
</script>

<style scoped>
.ps-digest-candidate-picker { display: flex; flex-direction: column; width: 100%; height: 100%; min-height: 0; }
.ps-candidate-filters { padding: 12px; flex-shrink: 0; border-bottom: 1px solid var(--ps-line-soft); }
.ps-candidate-filters > div { display: flex; gap: 8px; margin-top: 8px; }
.ps-candidate-filters .el-select { min-width: 0; flex: 1; }
.ps-candidate-filters small, .ps-candidate-note, .ps-candidate-pagination { color: var(--ps-muted); font-size: 12px; line-height: 1.65; }
.ps-candidate-filters small { display: block; margin-top: 8px; }
.ps-candidate-results { flex: 1; min-height: 0; overflow-y: auto; padding: 0 12px; }
.ps-candidate-result-list { list-style: none; padding: 0; margin: 0; }
.ps-candidate-result-list li { padding: 14px 0; border-bottom: 1px solid var(--ps-line-soft); }
.ps-candidate-result-list a { display: block; color: var(--ps-blue); font-size: 13px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; text-decoration: none; }
.ps-candidate-result-list a:hover { text-decoration: underline; }
.ps-candidate-result-list small, .ps-candidate-result-list time { display: block; color: var(--ps-muted); font-size: 12px; margin-top: 4px; overflow-wrap: anywhere; }
.ps-candidate-excerpt { margin: 6px 0; font-size: 12px; color: var(--ps-ink-2); line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ps-candidate-error { color: var(--ps-danger); font-size: 13px; overflow-wrap: anywhere; }
.ps-candidate-pagination { flex-shrink: 0; padding: 10px 12px; border-top: 1px solid var(--ps-line); background: #fff; }
.ps-candidate-pagination > div:first-child { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; }
.ps-candidate-pagination .el-select { width: 112px; }
.ps-candidate-pagination .el-pagination { justify-content: center; }
.ps-candidate-note { padding: 0 12px; }
</style>
