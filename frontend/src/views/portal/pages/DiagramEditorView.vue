<template>
  <div class="ps-diagram-page">
    <header class="ps-diagram-topbar">
      <div class="ps-editor-title">
        <button type="button" aria-label="返回报告" @click="router.back()"><ArrowLeft /></button>
        <span><strong>技术路线图编辑器</strong><small>多元检测数据缺陷智能化分析技术路线</small></span>
      </div>
      <div class="ps-diagram-settings">
        <el-select :model-value="diagram.diagramType" aria-label="图形类型" @change="value => updateSetting('diagramType', value)">
          <el-option label="技术路线图" value="route" /><el-option label="研究框架图" value="framework" /><el-option label="流程图" value="flow" />
        </el-select>
        <el-select :model-value="diagram.direction" aria-label="图形方向" @change="value => updateSetting('direction', value)">
          <el-option label="从左到右" value="lr" /><el-option label="从上到下" value="tb" />
        </el-select>
        <el-select :model-value="diagram.theme" aria-label="图形主题" @change="value => updateSetting('theme', value)">
          <el-option label="科技蓝" value="blue" /><el-option label="学术灰" value="gray" />
        </el-select>
      </div>
      <div class="ps-editor-actions">
        <el-button-group>
          <el-button :icon="RefreshLeft" :disabled="!canUndo" aria-label="撤销" @click="undo" />
          <el-button :icon="RefreshRight" :disabled="!canRedo" aria-label="重做" @click="redo" />
        </el-button-group>
        <el-button :loading="saving" @click="saveDiagram">保存成果</el-button>
        <el-button type="primary" @click="exportSvg"><Download />导出 SVG</el-button>
      </div>
    </header>

    <div class="ps-diagram-layout">
      <aside class="ps-node-library">
        <div class="ps-editor-panel-head"><span>节点库</span></div>
        <div v-for="group in nodeGroups" :key="group.title" class="ps-node-group">
          <h3>{{ group.title }}</h3>
          <button v-for="node in group.nodes" :key="node.label" type="button" :style="{ '--node-color': node.color }" @click="addNode(node)">
            <span><component :is="node.icon" /></span>{{ node.label }}
          </button>
        </div>
        <div class="ps-version-box">
          <h3>已保存版本</h3>
          <button type="button" :disabled="!savedAt || loading" @click="loadPersistedDiagram(true)">
            <span></span><span class="ps-local-version"><strong>{{ savedAt ? '最近保存' : '尚未保存' }}</strong><small>{{ savedAtLabel }}</small></span>
          </button>
          <p>当前会话保留 {{ history.length }} 个可撤销状态</p>
        </div>
      </aside>

      <main ref="canvasRef" class="ps-diagram-canvas">
        <div class="ps-canvas-tools">
          <button type="button" aria-label="放大" @click="setZoom(0.1)"><ZoomIn /></button>
          <span>{{ Math.round(zoom * 100) }}%</span>
          <button type="button" aria-label="缩小" @click="setZoom(-0.1)"><ZoomOut /></button>
          <button type="button" aria-label="全屏" @click="toggleFullscreen"><FullScreen /></button>
        </div>
        <div class="ps-flowchart" :class="[`is-${diagram.direction}`, `is-${diagram.theme}`]" :style="{ transform: `scale(${zoom})` }">
          <template v-for="(stage, index) in stageEntries" :key="stage.key">
            <section class="ps-flow-stage" :class="`is-${stage.className}`">
              <h3>{{ stage.title }}</h3>
              <div>
                <button
                  v-for="node in stage.nodes"
                  :key="node.id"
                  type="button"
                  :class="{ 'is-selected': selectedNodeId === node.id }"
                  :style="{ '--diagram-node-color': node.color }"
                  @click="selectedNodeId = node.id"
                >{{ node.label }}</button>
              </div>
            </section>
            <span v-if="index < stageEntries.length - 1" class="ps-flow-arrow"><Right /></span>
          </template>
        </div>
        <div class="ps-canvas-minimap" aria-hidden="true"><span :style="{ transform: `scale(${Math.min(zoom, 1)})` }"></span></div>
      </main>

      <aside class="ps-node-inspector">
        <div class="ps-editor-panel-head"><span>节点属性</span></div>
        <div v-if="selectedNode" class="ps-node-form">
          <label>节点名称<el-input :model-value="selectedNode.label" @change="value => updateSelectedNode('label', value)" /></label>
          <label>关联章节<el-select :model-value="selectedNode.linkedSection" @change="value => updateSelectedNode('linkedSection', value)"><el-option label="技术路线与试验方案" value="4" /><el-option label="研究目标与主要内容" value="3" /></el-select></label>
          <label>节点说明<el-input :model-value="selectedNode.description" type="textarea" :rows="4" @change="value => updateSelectedNode('description', value)" /></label>
          <label>填充颜色<el-color-picker :model-value="selectedNode.color" @change="value => updateSelectedNode('color', value || '#2764e7')" /></label>
          <div class="ps-style-controls">
            <button type="button" title="上移" aria-label="上移节点" @click="moveSelectedNode(-1)"><Top /></button>
            <button type="button" title="下移" aria-label="下移节点" @click="moveSelectedNode(1)"><Bottom /></button>
            <button type="button" title="复制" aria-label="复制节点" @click="duplicateSelectedNode"><CopyDocument /></button>
            <button type="button" class="is-danger" title="删除" aria-label="删除节点" @click="deleteSelectedNode"><Delete /></button>
          </div>
          <hr />
          <label>局部重新生成 / 调整要求<el-input v-model="regeneratePrompt" type="textarea" :rows="4" placeholder="描述希望如何调整该节点或分支" /></label>
          <el-button type="primary" class="ps-block-action" @click="applyNodeRequirement"><MagicStick />应用调整要求</el-button>
        </div>
        <div v-else class="ps-node-empty">在画布中选择节点以编辑属性</div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Bottom, CircleCheck, Connection, CopyDocument, Delete, Download, Finished, FullScreen, MagicStick, Operation, RefreshLeft, RefreshRight, Right, Top, TrendCharts, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { getPipelineResearchReportDiagram, updatePipelineResearchReportDiagram } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const canvasRef = ref()
const selectedNodeId = ref('analysis-clean')
const regeneratePrompt = ref('')
const zoom = ref(1)
const history = ref([])
const historyIndex = ref(-1)
const savedAt = ref('')
const saving = ref(false)
const loading = ref(false)

const stageDefinitions = [
  { key: 'input', title: '数据输入', className: 'input' },
  { key: 'analysis', title: '智能分析', className: 'core' },
  { key: 'validation', title: '验证评价', className: 'validation' },
  { key: 'output', title: '成果输出', className: 'result' }
]

const defaultDiagram = {
  schemaVersion: 1,
  diagramType: 'route',
  direction: 'lr',
  theme: 'blue',
  stages: {
    input: [
      createNode('input-mfl', '漏磁检测数据', '#2764e7', '汇总漏磁检测信号、里程和缺陷标注。'),
      createNode('input-ut', '超声检测数据', '#2764e7', '汇总超声壁厚与缺陷定量结果。'),
      createNode('input-stress', '应力监测数据', '#2764e7', '汇总应力监测序列与现场工况。')
    ],
    analysis: [
      createNode('analysis-clean', '数据清洗与标准化', '#0b8f87', '对多源检测数据进行清洗、时空对齐和特征标准化。'),
      createNode('analysis-align', '时空基准统一', '#0b8f87', '统一里程、时间和坐标参考系。'),
      createNode('analysis-fusion', '多源特征融合', '#0b8f87', '融合检测、工况与环境特征。'),
      createNode('analysis-recognition', '缺陷智能识别', '#0b8f87', '形成可解释的缺陷分类与定量结果。')
    ],
    validation: [
      createNode('validation-full', '足尺试验验证', '#c26a2e', '使用足尺试验验证方法稳定性。'),
      createNode('validation-excavate', '开挖数据验证', '#c26a2e', '使用开挖结果开展现场交叉验证。'),
      createNode('validation-metric', '模型性能评价', '#c26a2e', '评价准确率、召回率与工程适用边界。')
    ],
    output: [
      createNode('output-model', '缺陷识别模型', '#14845d', '输出可复现的缺陷识别模型。'),
      createNode('output-software', '工程应用软件', '#14845d', '形成面向现场业务的软件工具。'),
      createNode('output-standard', '技术标准建议', '#14845d', '沉淀工程应用和质量控制建议。')
    ]
  }
}

const diagram = ref(clone(defaultDiagram))
const nodeGroups = [
  { title: '基础节点', nodes: [{ label: '阶段', icon: Finished, color: '#2764e7' }, { label: '任务', icon: Operation, color: '#0b8f87' }, { label: '方法', icon: Connection, color: '#7357c8' }] },
  { title: '研究节点', nodes: [{ label: '验证', icon: CircleCheck, color: '#c26a2e' }, { label: '成果', icon: TrendCharts, color: '#14845d' }] }
]

const storageKey = computed(() => `pipesight:diagram:${route.params.id || 'default'}`)
const stageEntries = computed(() => stageDefinitions.map(stage => ({ ...stage, nodes: diagram.value.stages[stage.key] || [] })))
const selectedLocation = computed(() => {
  for (const stage of stageDefinitions) {
    const index = (diagram.value.stages[stage.key] || []).findIndex(node => node.id === selectedNodeId.value)
    if (index >= 0) return { stageKey: stage.key, index, node: diagram.value.stages[stage.key][index] }
  }
  return null
})
const selectedNode = computed(() => selectedLocation.value?.node || null)
const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value >= 0 && historyIndex.value < history.value.length - 1)
const savedAtLabel = computed(() => savedAt.value ? new Date(savedAt.value).toLocaleString('zh-CN', { hour12: false }) : '保存后可跨设备恢复')

function createNode(id, label, color, description = '') { return { id, label, color, description, linkedSection: '4' } }
function clone(value) { return JSON.parse(JSON.stringify(value)) }
function serialize() { return JSON.stringify(diagram.value) }
function makeId(prefix = 'node') { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }
function ensureSelection() {
  if (selectedLocation.value) return
  selectedNodeId.value = stageEntries.value.flatMap(stage => stage.nodes)[0]?.id || ''
}
function resetHistory() {
  history.value = [serialize()]
  historyIndex.value = 0
}
function recordSnapshot() {
  const snapshot = serialize()
  if (history.value[historyIndex.value] === snapshot) return
  history.value = history.value.slice(0, historyIndex.value + 1)
  history.value.push(snapshot)
  if (history.value.length > 50) history.value.shift()
  historyIndex.value = history.value.length - 1
}
function mutate(mutator) {
  mutator()
  recordSnapshot()
}
function restoreSnapshot(snapshot) {
  diagram.value = JSON.parse(snapshot)
  ensureSelection()
}
function undo() {
  if (!canUndo.value) return
  historyIndex.value -= 1
  restoreSnapshot(history.value[historyIndex.value])
}
function redo() {
  if (!canRedo.value) return
  historyIndex.value += 1
  restoreSnapshot(history.value[historyIndex.value])
}
function updateSetting(key, value) { mutate(() => { diagram.value[key] = value }) }
function updateSelectedNode(key, value) {
  if (!selectedNode.value) return
  const nextValue = key === 'label' ? String(value || '').trim() : value
  if (key === 'label' && !nextValue) return ElMessage.warning('节点名称不能为空')
  mutate(() => { selectedNode.value[key] = nextValue })
}
function addNode(template) {
  const node = createNode(makeId('analysis'), `新${template.label}`, template.color, `请补充“${template.label}”节点的输入、方法和输出说明。`)
  mutate(() => { diagram.value.stages.analysis.push(node) })
  selectedNodeId.value = node.id
}
function moveSelectedNode(offset) {
  const location = selectedLocation.value
  if (!location) return
  const nodes = diagram.value.stages[location.stageKey]
  const targetIndex = location.index + offset
  if (targetIndex < 0 || targetIndex >= nodes.length) return
  mutate(() => { [nodes[location.index], nodes[targetIndex]] = [nodes[targetIndex], nodes[location.index]] })
}
function duplicateSelectedNode() {
  const location = selectedLocation.value
  if (!location) return
  const duplicate = { ...clone(location.node), id: makeId(location.stageKey), label: `${location.node.label}（副本）` }
  mutate(() => { diagram.value.stages[location.stageKey].splice(location.index + 1, 0, duplicate) })
  selectedNodeId.value = duplicate.id
}
function deleteSelectedNode() {
  const location = selectedLocation.value
  if (!location) return
  const nodes = diagram.value.stages[location.stageKey]
  mutate(() => { nodes.splice(location.index, 1) })
  selectedNodeId.value = nodes[Math.min(location.index, nodes.length - 1)]?.id || ''
  ensureSelection()
}
function applyNodeRequirement() {
  const requirement = regeneratePrompt.value.trim()
  if (!selectedNode.value) return
  if (!requirement) return ElMessage.warning('请先填写节点调整要求')
  mutate(() => { selectedNode.value.description = `${selectedNode.value.description || ''}\n调整要求：${requirement}`.trim() })
  regeneratePrompt.value = ''
  ElMessage.success('调整要求已写入节点说明，可继续编辑或导出')
}
function setZoom(delta) { zoom.value = Math.min(1.5, Math.max(0.5, Number((zoom.value + delta).toFixed(1)))) }
async function toggleFullscreen() {
  if (!canvasRef.value?.requestFullscreen) return ElMessage.warning('当前浏览器不支持画布全屏')
  try { await canvasRef.value.requestFullscreen() } catch (error) { ElMessage.warning('无法进入全屏，请检查浏览器权限') }
}
function saveLocalBackup(payload) {
  localStorage.setItem(storageKey.value, JSON.stringify(payload))
}
async function saveDiagram() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = { schemaVersion: 1, savedAt: new Date().toISOString(), diagram: clone(diagram.value) }
    saveLocalBackup(payload)
    const res = await updatePipelineResearchReportDiagram(String(route.params.id), {
      schemaVersion: payload.schemaVersion,
      diagram: payload.diagram
    })
    savedAt.value = res.data?.savedAt || payload.savedAt
    saveLocalBackup({ ...payload, savedAt: savedAt.value })
    ElMessage.success('图形成果已保存，可跨设备恢复')
  } catch (error) {
    ElMessage.error('服务端保存失败，已尽可能保留本机备份')
  } finally {
    saving.value = false
  }
}
function readSavedDiagram() {
  const raw = localStorage.getItem(storageKey.value)
  if (!raw) return null
  const payload = JSON.parse(raw)
  if (!payload?.diagram?.stages || payload.schemaVersion !== 1) throw new Error('invalid diagram')
  return payload
}
function restoreLocalDiagram(showMessage = true) {
  try {
    const payload = readSavedDiagram()
    if (!payload) return
    diagram.value = clone(payload.diagram)
    savedAt.value = payload.savedAt || ''
    ensureSelection()
    resetHistory()
    if (showMessage) ElMessage.success('已恢复本机备份图形')
  } catch (error) {
    ElMessage.warning('本地图形数据无法读取，已保留默认结构')
  }
}
function applyPersistedDiagram(payload) {
  if (!payload?.diagram?.stages) return false
  diagram.value = clone(payload.diagram)
  savedAt.value = payload.savedAt || ''
  ensureSelection()
  resetHistory()
  return true
}
async function loadPersistedDiagram(showMessage = false) {
  if (loading.value) return
  loading.value = true
  try {
    const res = await getPipelineResearchReportDiagram(String(route.params.id))
    if (applyPersistedDiagram(res.data)) {
      saveLocalBackup({ schemaVersion: res.data.schemaVersion || 1, savedAt: res.data.savedAt, diagram: clone(res.data.diagram) })
      if (showMessage) ElMessage.success('已恢复账号下最近保存的图形')
      return
    }
    restoreLocalDiagram(showMessage)
  } catch (error) {
    try {
      const local = readSavedDiagram()
      if (local) {
        applyPersistedDiagram(local)
        if (showMessage) ElMessage.warning('服务端版本暂不可用，已恢复本机备份')
      } else if (showMessage) {
        ElMessage.error('暂时无法读取已保存图形')
      }
    } catch (localError) {
      if (showMessage) ElMessage.error('服务端和本机备份均无法读取')
    }
  } finally {
    loading.value = false
  }
}
function escapeXml(value) { return String(value ?? '').replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[char]) }
function svgDocument() {
  const isVertical = diagram.value.direction === 'tb'
  const stageWidth = isVertical ? 560 : 220
  const gap = isVertical ? 58 : 76
  const maxStageHeight = Math.max(...stageEntries.value.map(stage => 92 + stage.nodes.length * 46), 220)
  const width = isVertical ? 760 : 80 + stageEntries.value.length * stageWidth + (stageEntries.value.length - 1) * gap
  const height = isVertical ? 80 + stageEntries.value.length * maxStageHeight + (stageEntries.value.length - 1) * gap : maxStageHeight + 160
  const background = diagram.value.theme === 'gray' ? '#f4f5f7' : '#f5f8fd'
  const stageColors = { input: '#2764e7', analysis: '#0b8f87', validation: '#c26a2e', output: '#14845d' }
  const parts = [`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`, `<title>${escapeXml('多元检测数据缺陷智能化分析技术路线')}</title>`, '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#8290a3"/></marker></defs>', `<rect width="100%" height="100%" fill="${background}"/>`]
  stageEntries.value.forEach((stage, index) => {
    const x = isVertical ? (width - stageWidth) / 2 : 40 + index * (stageWidth + gap)
    const y = isVertical ? 40 + index * (maxStageHeight + gap) : 80
    const color = stageColors[stage.key]
    parts.push(`<rect x="${x}" y="${y}" width="${stageWidth}" height="${maxStageHeight}" rx="16" fill="#ffffff" stroke="${color}" stroke-width="2"/>`)
    parts.push(`<text x="${x + stageWidth / 2}" y="${y + 34}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="18" font-weight="700" fill="${color}">${escapeXml(stage.title)}</text>`)
    stage.nodes.forEach((node, nodeIndex) => {
      const nodeX = x + 18
      const nodeY = y + 58 + nodeIndex * 46
      parts.push(`<rect x="${nodeX}" y="${nodeY}" width="${stageWidth - 36}" height="34" rx="7" fill="#ffffff" stroke="${escapeXml(node.color || color)}"/>`)
      parts.push(`<text x="${x + stageWidth / 2}" y="${nodeY + 22}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="13" fill="#26364a">${escapeXml(String(node.label).slice(0, 28))}</text>`)
    })
    if (index < stageEntries.value.length - 1) {
      const line = isVertical
        ? { x1: width / 2, y1: y + maxStageHeight + 10, x2: width / 2, y2: y + maxStageHeight + gap - 10 }
        : { x1: x + stageWidth + 10, y1: y + maxStageHeight / 2, x2: x + stageWidth + gap - 10, y2: y + maxStageHeight / 2 }
      parts.push(`<line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" stroke="#8290a3" stroke-width="2" marker-end="url(#arrow)"/>`)
    }
  })
  parts.push('</svg>')
  return parts.join('')
}
function exportSvg() {
  try {
    const blob = new Blob([svgDocument()], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `技术路线图-${new Date().toISOString().slice(0, 10)}.svg`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('SVG 文件已导出')
  } catch (error) {
    ElMessage.error('SVG 导出失败')
  }
}
function handleKeyboardShortcut(event) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'z') return
  if (event.target instanceof HTMLElement && (event.target.matches('input, textarea') || event.target.isContentEditable)) return
  event.preventDefault()
  event.shiftKey ? redo() : undo()
}

onMounted(async () => {
  await loadPersistedDiagram(false)
  if (!history.value.length) resetHistory()
  window.addEventListener('keydown', handleKeyboardShortcut)
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeyboardShortcut))
</script>
