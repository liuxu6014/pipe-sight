<template>
  <div class="ps-ask-page">
    <aside class="ps-ask-scope">
      <div class="ps-editor-panel-head"><span>检索范围</span></div>
      <button type="button" :class="{ 'is-active': scope === 'all' }" @click="useAllScope">
        <Files /><span><strong>全部授权知识库</strong><small>{{ knowledgeDocuments.length }} 份资料</small></span><Check v-if="scope === 'all'" />
      </button>
      <h3>按分类选择</h3>
      <label v-for="type in documentTypes" :key="type">
        <el-checkbox v-model="selectedTypes" :value="type" @change="syncTypeScope" />{{ type }}<span>{{ countByType(type) }}</span>
      </label>
      <h3>指定资料</h3>
      <div v-if="portalStore.dataLoading && !portalStore.dataLoaded" class="ps-scope-loading"><i></i><i></i><i></i></div>
      <div v-else-if="!knowledgeDocuments.length" class="ps-scope-empty">
        <DocumentDelete /><span>暂无授权资料</span><button type="button" @click="router.push('/portal/knowledge')">去上传</button>
      </div>
      <button v-for="doc in availableDocuments" v-else :key="doc.id" type="button" class="ps-scope-doc" :class="{ 'is-active': selectedDocs.includes(String(doc.id)) }" :disabled="doc.status !== '已解析'" @click="toggleDocument(String(doc.id))">
        <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
        <span><strong>{{ doc.name }}</strong><small>{{ doc.status === '已解析' ? `${doc.pages ? `${doc.pages} 页 · ` : ''}${doc.permission}` : doc.status }}</small></span>
        <Check v-if="selectedDocs.includes(String(doc.id))" />
      </button>
    </aside>

    <main class="ps-chat-main">
      <header>
        <div><span class="ps-ai-orb"><MagicStick /></span><span><strong>知识问答</strong><small>回答仅基于当前账号可访问的资料</small></span></div>
        <button type="button" @click="newConversation"><Plus />新会话</button>
      </header>

      <div ref="messageListRef" class="ps-message-list" aria-live="polite">
        <div v-if="portalStore.dataError" class="ps-chat-service-state" role="status">
          <WarningFilled /><span>{{ portalStore.dataError }}</span><button type="button" @click="portalStore.hydrate(true)">重试</button>
        </div>

        <div v-if="!messages.length" class="ps-chat-welcome">
          <span class="ps-ai-orb large"><MagicStick /></span>
          <h1>从授权资料中找到可靠答案</h1>
          <p>回答会附带来源资料和原文片段；证据不足时会明确说明。</p>
          <div>
            <button v-for="suggestion in suggestedQuestions" :key="suggestion" type="button" :disabled="!knowledgeDocuments.length" @click="ask(suggestion)">{{ suggestion }}<ArrowRight /></button>
          </div>
        </div>

        <template v-for="message in messages" :key="message.id">
          <div v-if="message.role === 'user'" class="ps-user-message"><div>{{ message.content }}</div><span>{{ currentUserName.slice(0, 1) }}</span></div>
          <div v-else class="ps-ai-message" :class="{ 'is-error': message.error }">
            <span class="ps-ai-orb"><MagicStick /></span>
            <div>
              <div v-if="message.loading" class="ps-thinking"><i></i><i></i><i></i><span>正在检索授权资料并核对证据</span></div>
              <template v-else>
                <p v-for="paragraph in message.content" :key="paragraph">{{ paragraph }}</p>
                <button v-if="message.error" type="button" class="ps-answer-retry" @click="retryAnswer(message)"><RefreshRight />重新提问</button>
                <div v-if="message.citations.length" class="ps-answer-citations">
                  <button v-for="citation in message.citations" :key="citation.id" type="button" @click="openCitation(citation)">
                    <span>{{ citation.index }}</span><div><strong>{{ citation.title }}</strong><small>{{ citation.location }}</small><p>{{ citation.quote }}</p></div><TopRight />
                  </button>
                </div>
                <div v-if="!message.error" class="ps-answer-actions">
                  <button type="button" @click="copyAnswer(message)"><DocumentCopy />复制回答</button>
                  <button type="button" :disabled="!message.citations.length" @click="addAnswerSources(message)"><Collection />引用加入资料篮</button>
                  <button type="button" @click="createReport(message)"><EditPen />转为报告任务</button>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>

      <footer class="ps-chat-composer">
        <div class="ps-selected-scope">检索范围：{{ scopeLabel }}<button v-if="selectedDocs.length || selectedTypes.length" type="button" @click="useAllScope">恢复全部资料</button></div>
        <div>
          <textarea v-model="question" rows="2" :disabled="answerInFlight || !knowledgeDocuments.length" maxlength="1000" placeholder="请输入需要从资料中查找的问题，Shift + Enter 换行" @keydown.enter.exact.prevent="submitQuestion"></textarea>
          <button type="button" :disabled="!question.trim() || answerInFlight || !knowledgeDocuments.length" :aria-label="answerInFlight ? '正在生成回答' : '发送问题'" @click="submitQuestion"><Promotion /></button>
        </div>
        <small>{{ question.length }}/1000 · 回答由授权资料检索与证据编排生成，请结合引用原文判断。</small>
      </footer>
    </main>

    <aside class="ps-chat-history">
      <div class="ps-editor-panel-head"><span>本次会话</span></div>
      <button v-for="item in conversationHistory" :key="item.id" type="button" @click="question = item.content">
        <ChatLineRound /><span><strong>{{ item.content }}</strong><small>点击可再次编辑提问</small></span><ArrowRight />
      </button>
      <div v-if="!conversationHistory.length" class="ps-history-empty">发送第一个问题后，会话问题会显示在这里。</div>
      <div class="ps-selected-docs">
        <h3>已选资料 <span>{{ selectedDocs.length }}</span></h3>
        <div v-for="doc in chosenDocuments" :key="doc.id">
          <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
          <span><strong>{{ doc.name }}</strong><small>{{ doc.pages ? `${doc.pages} 页` : '页数待补充' }}</small></span>
          <button type="button" :aria-label="`移除${doc.name}`" @click="toggleDocument(String(doc.id))"><Close /></button>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, ChatLineRound, Check, Close, Collection, DocumentCopy, DocumentDelete, EditPen, Files, MagicStick, Plus, Promotion, RefreshRight, TopRight, WarningFilled } from '@element-plus/icons-vue'
import { askPipelineKnowledge } from '@/api/pipeline/intelligence'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const userStore = useUserStore()
const scope = ref(route.query.doc ? 'selected' : 'all')
const selectedTypes = ref([])
const selectedDocs = ref(route.query.doc ? [String(route.query.doc)] : [])
const question = ref('')
const messages = ref([])
const messageListRef = ref()
const answerInFlight = ref(false)
const documentTypes = ['内部文献', '英文报告', '论文', '历史项目', '模板', '其他']
const suggestedQuestions = ['多元检测数据融合的关键技术难点是什么？', '磁各向异性应力监测有哪些现场影响因素？', '请比较国内外管道完整性管理实践差异']
let requestSerial = 0

const knowledgeDocuments = computed(() => portalStore.knowledgeDocuments || [])
const availableDocuments = computed(() => knowledgeDocuments.value.slice(0, 8))
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const chosenDocuments = computed(() => knowledgeDocuments.value.filter(item => selectedDocs.value.includes(String(item.id))))
const conversationHistory = computed(() => messages.value.filter(item => item.role === 'user').slice().reverse())
const scopeLabel = computed(() => selectedDocs.value.length ? `指定 ${selectedDocs.value.length} 份资料` : selectedTypes.value.length ? selectedTypes.value.join('、') : '全部授权知识库')

function countByType(type) { return knowledgeDocuments.value.filter(item => item.type === type).length }
function toggleDocument(id) {
  selectedDocs.value = selectedDocs.value.includes(id) ? selectedDocs.value.filter(item => item !== id) : [...selectedDocs.value, id]
  scope.value = selectedDocs.value.length ? 'selected' : selectedTypes.value.length ? 'types' : 'all'
}
function syncTypeScope() { selectedDocs.value = []; scope.value = selectedTypes.value.length ? 'types' : 'all' }
function useAllScope() { selectedDocs.value = []; selectedTypes.value = []; scope.value = 'all' }
function ask(value) { question.value = value; submitQuestion() }
function normalizeCitation(reference, index) {
  const docId = String(reference.id || reference.docId || reference.materialId || '')
  return {
    ...reference,
    id: `${docId || 'reference'}-${index}`,
    index: `[${index + 1}]`,
    docId,
    title: reference.name || reference.title || `授权资料 ${index + 1}`,
    location: reference.location || `${reference.type || '知识库资料'}${reference.pages ? ` · ${reference.pages} 页` : ''}`,
    quote: reference.quote || reference.scenario || reference.summary || (reference.keywords?.length ? `关键词：${reference.keywords.join('、')}` : '请打开原文核对相关证据。')
  }
}
function filterReferences(references) {
  if (selectedDocs.value.length) return references.filter(item => selectedDocs.value.includes(String(item.id || item.docId || item.materialId)))
  if (selectedTypes.value.length) return references.filter(item => selectedTypes.value.includes(item.type || item.category))
  return references
}
async function submitQuestion() {
  const content = question.value.trim()
  if (!content || answerInFlight.value || !knowledgeDocuments.value.length) return
  const requestId = ++requestSerial
  const userMessage = { id: `${Date.now()}-q`, role: 'user', content }
  const answerId = `${Date.now()}-a`
  messages.value.push(userMessage, { id: answerId, role: 'assistant', question: content, loading: true, error: false, content: [], citations: [] })
  question.value = ''
  answerInFlight.value = true
  scrollBottom()
  try {
    const res = await askPipelineKnowledge(content, { documentIds: selectedDocs.value, documentTypes: selectedTypes.value })
    if (requestId !== requestSerial) return
    const allReferences = Array.isArray(res.data?.references) ? res.data.references : []
    const references = filterReferences(allReferences)
    const hasScopedFilter = selectedDocs.value.length > 0 || selectedTypes.value.length > 0
    const answer = String(res.data?.answer || '').trim()
    const paragraphs = hasScopedFilter && !references.length
      ? ['当前授权资料不足，所选范围内没有检索到可验证的引用证据。请调整问题或扩大检索范围后重试。']
      : answer.split(/\n+/).filter(Boolean)
    if (!paragraphs.length) paragraphs.push('当前授权资料不足，知识库未返回可验证的有效答案，请调整问题后重试。')
    else if (!references.length && !hasScopedFilter) paragraphs.push('当前授权资料不足，未检索到可验证的引用证据，请结合原始资料复核。')
    const target = messages.value.find(item => item.id === answerId)
    if (target) Object.assign(target, { loading: false, content: paragraphs, citations: references.map(normalizeCitation) })
  } catch (error) {
    if (requestId !== requestSerial) return
    const target = messages.value.find(item => item.id === answerId)
    if (target) Object.assign(target, {
      loading: false,
      error: true,
      content: ['实时知识服务暂不可用，本次问题没有生成演示答案，也不会伪造引用。请检查后端服务后重新提问。'],
      citations: []
    })
  } finally {
    if (requestId === requestSerial) answerInFlight.value = false
    scrollBottom()
  }
}
function retryAnswer(message) { question.value = message.question; submitQuestion() }
function scrollBottom() { nextTick(() => { if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight }) }
function newConversation() { requestSerial += 1; answerInFlight.value = false; messages.value = []; question.value = '' }
function openCitation(citation) { if (citation.docId) router.push(`/portal/knowledge/${citation.docId}`) }
async function copyAnswer(message) {
  const text = [...message.content, ...message.citations.map(item => `${item.index} ${item.title} ${item.location}`)].join('\n')
  try { await navigator.clipboard.writeText(text); ElMessage.success('回答及引用已复制') } catch (error) { ElMessage.error('复制失败，请手动选择文本') }
}
function addAnswerSources(message) {
  const added = message.citations.reduce((count, citation) => count + (portalStore.addToBasket({ id: citation.docId || citation.id, title: citation.title, type: '知识库资料' }) ? 1 : 0), 0)
  ElMessage.success(added ? `已将 ${added} 份引用资料加入资料篮` : '引用资料已在资料篮中')
}
function createReport(message) {
  router.push({ path: '/portal/research/create', query: { question: message.question, docs: message.citations.map(item => item.docId).filter(Boolean).join(',') } })
}

watch(knowledgeDocuments, documents => {
  const ids = new Set(documents.map(item => String(item.id)))
  selectedDocs.value = selectedDocs.value.filter(id => ids.has(id))
  if (!selectedDocs.value.length && scope.value === 'selected') scope.value = selectedTypes.value.length ? 'types' : 'all'
})
onMounted(() => portalStore.hydrate())
</script>
