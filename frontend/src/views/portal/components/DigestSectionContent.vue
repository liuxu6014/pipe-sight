<template>
  <div v-stable-caret ref="contentElement" class="ps-digest-content" :contenteditable="editable" @input="syncContent" @compositionend="syncContent">
    <template v-for="(block, index) in blocks" :key="index">
      <h3 v-if="block.role === 'event'" data-role="event">{{ block.text }}</h3>
      <p v-else :class="`ps-digest-${block.role}`" :data-role="block.role" :data-url="block.url" :data-number="block.number">
        <template v-if="block.role === 'source' && block.url">{{ block.number }} <a :href="block.url" target="_blank" rel="noopener noreferrer" @click="editable && $event.preventDefault()">{{ editable ? block.text : cleanSource(block.text) }}</a></template>
        <template v-else-if="block.label"><strong>{{ block.label }}</strong>{{ block.text }}</template>
        <template v-else>{{ block.role === 'source' && !editable ? cleanSource(block.text) : block.text }}</template>
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { vStableCaret } from '@/utils/portal/stableCaret'
import { cleanSource } from '@/utils/portal/discovery'
const props = defineProps({ content: { type: String, default: '' }, editable: Boolean })
const emit = defineEmits(['update:content'])
const contentElement = ref()
function syncContent(event) {
  if (!props.editable || event.isComposing) return
  const lines = Array.from(contentElement.value.children).map(node => {
    const text = node.innerText.trim()
    if (node.dataset.role === 'event') return `### ${text}`
    if (node.dataset.role === 'source' && node.dataset.url) {
      const number = node.dataset.number
      return `${number} [${text.replace(/^\[\d+\]\s*/, '')}](${node.dataset.url})`
    }
    return text
  }).filter(Boolean)
  emit('update:content', lines.join('\n\n'))
}
const blocks = computed(() => props.content.split(/\n+/).filter(line => line.trim()).map(line => {
  const text = line.trim()
  if (text.startsWith('### ')) return { role: 'event', text: text.slice(4) }
  for (const [prefix, role] of [['发布时间：', 'published'], ['行业洞察：', 'insight']]) {
    if (text.startsWith(prefix)) return { role, label: prefix, text: text.slice(prefix.length) }
  }
  if (text === '数据源：') return { role: 'source-label', text }
  const source = text.match(/^(\[\d+\]) \[(.+)\]\((https?:\/\/[^\s]+)\)$/)
  if (source) return { role: 'source', number: source[1], text: source[2], url: source[3] }
  if (/^\[\d+\] /.test(text)) return { role: 'source', text }
  return { role: 'summary', text }
}))
</script>

<style scoped>
.ps-digest-content { font-size: 16px; line-height: 1.75; color: #111; overflow-wrap: anywhere; }
h3 { font-size: 18px; font-weight: 700; line-height: 1.6; margin: 22px 0 12px; }
p { margin: 12px 0; }
.ps-digest-summary { text-indent: 2em; }
.ps-digest-published, .ps-digest-insight, .ps-digest-source-label, .ps-digest-source { padding: 10px 14px; }
.ps-digest-published { background: #f8fbf6; }
.ps-digest-insight { background: #fefcf2; }
.ps-digest-insight strong { text-decoration: underline; }
.ps-digest-source-label, .ps-digest-source { background: #f6f8fc; margin: 0; padding-block: 10px; }
.ps-digest-source-label { font-weight: 700; margin-top: 16px; }
a { color: #00e; text-decoration: underline; }
@media (max-width: 768px) { .ps-digest-content { font-size: 16px; } h3 { font-size: 18px; } }
</style>
