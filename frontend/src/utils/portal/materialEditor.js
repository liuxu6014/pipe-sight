import { computed, reactive, ref } from 'vue'

export function useMaterialEditor({ update, onSaved = () => {} }) {
  const visible = ref(false), saving = ref(false), error = ref('')
  const draft = reactive({ id: '', name: '', text: '', version: null })
  let original = { name: '', text: '' }
  const dirty = computed(() => visible.value && (draft.name !== original.name || draft.text !== original.text))
  async function canLeave(confirmDiscard) {
    if (saving.value) return false
    if (!dirty.value) return true
    return Boolean(await confirmDiscard())
  }
  function open(document) {
    if (saving.value || document?.canManage !== true || !document.id || !Number.isInteger(document.versionNo)) return false
    const text = document.editedText ?? document.edited_text ?? document.extractedText ?? document.extracted_text ?? document.content
    // A list row has a revision and permissions, but not the actual editable body.
    if (text === undefined || text === null) return false
    Object.assign(draft, {
      id: String(document.id), name: document.name || '', version: document.versionNo,
      text: String(text)
    })
    error.value = ''
    original = { name: draft.name, text: draft.text }
    visible.value = true
    return true
  }
  async function save() {
    if (!visible.value || saving.value) return false
    error.value = ''
    if (!draft.name.trim() || draft.name.trim().length > 255) {
      error.value = '请填写资料名称，最多 255 个字符'
      return false
    }
    if (!draft.text.trim()) {
      error.value = '请填写资料正文，以便用于检索和报告生成'
      return false
    }
    const id = draft.id
    const payload = { expectedVersion: draft.version, name: draft.name.trim(), editedText: draft.text }
    saving.value = true
    try {
      const response = await update(id, payload)
      const document = response.data?.data || response.data
      if (!document?.id || String(document.id) !== id) throw new Error('保存响应缺少有效资料信息，请重新加载确认；当前输入已保留')
      onSaved(document)
      visible.value = false
      return true
    } catch (exception) {
      error.value = exception?.msg || exception?.message || '保存失败，当前输入已保留，请稍后重试'
      return false
    } finally {
      saving.value = false
    }
  }
  return { visible, saving, error, draft, dirty, canLeave, open, save }
}
