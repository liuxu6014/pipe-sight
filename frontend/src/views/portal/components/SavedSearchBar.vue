<template>
  <div class="ps-saved-search-bar" aria-label="当前筛选与常用条件">
    <div class="ps-query-chips" aria-label="当前筛选">
      <el-tag v-for="chip in queryState.chips" :key="`${chip.field}:${chip.value}`" closable @close="removeFilter(chip)">{{ chip.label }}</el-tag>
      <span v-if="!queryState.chips.length">{{ queryState.error || '未设置筛选条件' }}</span>
    </div>
    <el-popover trigger="click" placement="bottom-end" width="min(360px, calc(100vw - 24px))" @show="loadSaved">
      <template #reference><el-button :disabled="!account">{{ account ? `常用条件${saved.length ? ` · ${saved.length}` : ''}` : '登录后保存条件' }}</el-button></template>
      <div class="ps-saved-search-panel">
        <strong>常用检索条件</strong>
        <p>仅保存在当前浏览器，按账号隔离；本页最多 12 组。相同条件再次保存会更新名称，不保存正文或文件。共享电脑请勿保存敏感关键词。</p>
        <label>条件名称<el-input v-model.trim="name" maxlength="50" aria-label="检索条件名称" placeholder="例如：近一年管道检测论文" @keydown.enter="saveCurrent" /></label>
        <el-button type="primary" :disabled="!canSave" @click="saveCurrent">保存当前条件</el-button>
        <p v-if="error" class="ps-saved-search-error" role="alert">{{ error }}</p>
        <ul v-if="saved.length">
          <li v-for="entry in saved" :key="entry.id"><button type="button" class="ps-saved-search-apply" :aria-label="`应用条件：${entry.name}`" @click="applyEntry(entry)"><strong>{{ entry.name }}</strong><small>{{ summary(entry.filters) }}</small></button><el-button plain type="danger" :aria-label="`移除条件：${entry.name}`" @click="removeEntry(entry)">移除</el-button></li>
        </ul>
        <p v-else-if="!error">尚未保存条件。先设置筛选，再输入名称保存。</p>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import useUserStore from '@/store/modules/user'
import { decimalId } from '@/utils/portal/businessId'
import { createSavedSearchRepository, normalizeSearchFilters, searchFilterChips, withoutSearchFilter } from '@/utils/portal/savedSearches'

const props = defineProps({ kind: { type: String, required: true }, query: { type: Object, required: true } })
const emit = defineEmits(['apply'])
const userStore = useUserStore()
const account = computed(() => decimalId(userStore.id))
const saved = ref([])
const name = ref('')
const error = ref('')
let disposed = false
const queryState = computed(() => {
  try { return { chips: searchFilterChips(props.kind, props.query), error: '' } }
  catch (failure) { return { chips: [], error: failure.message } }
})
const canSave = computed(() => Boolean(account.value && name.value && queryState.value.chips.length && !queryState.value.error))
function repository() {
  let storage
  try { storage = window.localStorage } catch { throw new Error('当前浏览器不允许保存条件，请检查存储权限') }
  return createSavedSearchRepository(storage, account.value, props.kind)
}
function loadSaved() {
  saved.value = []; error.value = ''
  if (!account.value || typeof window === 'undefined') return
  try { saved.value = repository().list() } catch (failure) { error.value = failure.message }
}
function summary(filters) { return searchFilterChips(props.kind, filters).map(item => item.label).join(' / ') }
function saveCurrent() {
  if (!canSave.value) return
  try { saved.value = repository().save(name.value, props.query); error.value = ''; ElMessage.success('条件已保存在当前浏览器') }
  catch (failure) { error.value = failure.message }
}
function applyEntry(entry) {
  try { emit('apply', normalizeSearchFilters(props.kind, entry.filters)); error.value = '' }
  catch (failure) { error.value = failure.message }
}
function removeFilter(chip) { emit('apply', withoutSearchFilter(props.kind, props.query, chip)) }
async function removeEntry(entry) {
  const owner = account.value, kind = props.kind
  try {
    await ElMessageBox.confirm(`移除常用条件“${entry.name}”？不会删除文章、资料或报告。`, '移除常用条件', { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' })
    if (disposed || owner !== account.value || kind !== props.kind) return
    saved.value = repository().remove(entry.id); error.value = ''
  } catch (failure) { if (failure !== 'cancel' && failure !== 'close') error.value = failure.message || '移除失败，请重试' }
}
function storageChanged(event) {
  if (!account.value) return
  try { if (event.key === null || event.key === repository().key) loadSaved() } catch (failure) { error.value = failure.message }
}
watch([account, () => props.kind], () => { name.value = ''; loadSaved() }, { immediate: true, flush: 'sync' })
onMounted(() => window.addEventListener('storage', storageChanged))
onBeforeUnmount(() => { disposed = true; window.removeEventListener('storage', storageChanged) })
</script>

<style scoped>
.ps-saved-search-bar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin: 10px 0 14px; }
.ps-query-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.ps-query-chips > span:not(.el-tag) { color: var(--ps-muted); font-size: 13px; }
.ps-query-chips :deep(.el-tag) { max-width: 100%; height: auto; min-height: 28px; white-space: normal; overflow-wrap: anywhere; }
.ps-query-chips :deep(.el-tag__content) { white-space: normal; overflow-wrap: anywhere; }
.ps-saved-search-panel { color: var(--el-text-color-primary); }
.ps-saved-search-panel > p { font-size: 13px; line-height: 1.6; color: var(--el-text-color-regular); }
.ps-saved-search-panel label { display: block; font-size: 13px; }
.ps-saved-search-panel label :deep(.el-input) { margin: 6px 0 10px; }
.ps-saved-search-panel ul { list-style: none; margin: 14px 0 0; padding: 0; max-height: 320px; overflow-y: auto; }
.ps-saved-search-panel li { display: flex; align-items: center; gap: 8px; border-top: 1px solid var(--el-border-color-light); padding: 10px 0; }
.ps-saved-search-apply { flex: 1; min-width: 0; padding: 4px; border: 0; background: transparent; text-align: left; color: inherit; cursor: pointer; }
.ps-saved-search-apply:hover { background: var(--el-fill-color-light); }
.ps-saved-search-apply strong, .ps-saved-search-apply small { display: block; overflow-wrap: anywhere; }
.ps-saved-search-apply small { margin-top: 5px; line-height: 1.5; color: var(--el-text-color-secondary); }
.ps-saved-search-panel .ps-saved-search-error { color: var(--el-color-danger); }
</style>
