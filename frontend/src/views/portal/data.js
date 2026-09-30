export const portalNavigation = [
  { label: '首页', path: '/portal', match: path => path === '/portal' },
  { label: '科技资讯', path: '/portal/news', match: path => path.startsWith('/portal/news') },
  { label: '论文资料', path: '/portal/papers', match: path => path.startsWith('/portal/papers') },
  { label: '科研工作台', path: '/portal/research', match: path => path.startsWith('/portal/research') },
  { label: '情报简报', path: '/portal/digests', match: path => path.startsWith('/portal/digests') },
  { label: '知识库', path: '/portal/knowledge', match: path => path.startsWith('/portal/knowledge') }
]

export const topics = [
  { name: '管道本体应力监测', heat: 96, count: 38, trend: '+12%' },
  { name: '多元检测数据融合', heat: 91, count: 31, trend: '+8%' },
  { name: '高后果区风险评价', heat: 86, count: 27, trend: '+5%' },
  { name: '腐蚀防护与完整性', heat: 82, count: 24, trend: '+9%' },
  { name: '智能阴保监测', heat: 76, count: 19, trend: '+3%' },
  { name: '数字孪生管网', heat: 72, count: 16, trend: '+6%' }
]

export const newsItems = [
  {
    id: 'news-001',
    title: '管道多元检测数据智能化分析进入工程化验证阶段',
    source: '能源科技观察',
    sourceType: '新闻网站',
    time: '2026-08-04 09:30',
    category: '检测技术',
    importance: '重点',
    summary: '漏磁、超声、应力与外检测数据正在通过统一时空基准完成关联分析，为缺陷复核和维修排序提供可解释依据。',
    tags: ['多元检测', '缺陷识别', '完整性管理'],
    body: [
      '近期多项工程试验表明，单一检测手段难以完整覆盖复杂管段的风险特征。将漏磁、超声、应力监测、地质灾害和历史维修记录统一到同一里程坐标后，可显著提高异常识别的可信度。',
      '该技术路线的关键不只是模型精度，还包括数据质量分级、检测偏差校准和结果可追溯。项目团队正在形成从数据入库、特征融合、风险评分到人工复核的闭环流程。',
      '对管网运营单位而言，多元融合结果可直接支撑开挖验证、维修计划和年度完整性评价，下一阶段应重点验证跨管线迁移能力与小样本场景稳定性。'
    ]
  },
  {
    id: 'news-002',
    title: '油气管道应力监测向在线化与智能预警持续演进',
    source: '管道技术前沿',
    sourceType: '微信公众号',
    time: '2026-08-03 16:20',
    category: '应力监测',
    importance: '重点',
    summary: '磁各向异性、光纤传感与数字孪生模型结合，可为高风险管段提供连续状态评估与分级预警。',
    tags: ['应力监测', '数字孪生', '风险预警'],
    body: ['在线应力监测正由单点测量走向多源协同。', '连续监测数据需要与温压工况、地质位移和历史缺陷共同解释。', '工程落地需同步建立阈值标定、误报复核与设备维护机制。']
  },
  {
    id: 'news-003',
    title: '面向高后果区的管道风险动态评价方法发布',
    source: '国际管道研究中心',
    sourceType: '新闻网站',
    time: '2026-08-02 11:10',
    category: '管网安全',
    importance: '一般',
    summary: '新方法将人口、环境敏感点、第三方施工和管体状态纳入动态风险画像，支持按月更新处置优先级。',
    tags: ['高后果区', '动态评价', '风险画像'],
    body: ['动态评价将静态台账转化为可更新的风险画像。', '变化检测是实现月度更新的核心。', '建议与巡线、施工报备和隐患治理工单联动。']
  },
  {
    id: 'news-004',
    title: '智能阴极保护系统开始引入边缘计算与异常诊断',
    source: '腐蚀与防护学会',
    sourceType: '微信公众号',
    time: '2026-08-01 14:35',
    category: '腐蚀防护',
    importance: '一般',
    summary: '边缘设备可在通信不稳定区域完成断电电位计算和异常识别，降低数据缺失对保护效果判断的影响。',
    tags: ['阴极保护', '边缘计算', '异常诊断'],
    body: ['智能阴保终端正在提升本地计算能力。', '本地诊断可减少通信波动造成的误判。', '设备安全与远程升级机制仍需重点验证。']
  },
  {
    id: 'news-005',
    title: '长输管道无人机巡检形成“发现—复核—闭环”新流程',
    source: '油气储运数字化',
    sourceType: '新闻网站',
    time: '2026-07-31 10:05',
    category: '智能巡检',
    importance: '一般',
    summary: '无人机影像识别结果与线路桩、施工报备和巡线工单联动，缩短第三方施工隐患处置时间。',
    tags: ['无人机', '智能巡检', '第三方施工'],
    body: ['无人机巡检需要与业务工单深度结合。', '影像模型应提供可复核的证据截图。', '闭环时效比单纯识别率更能体现工程价值。']
  },
  {
    id: 'news-006',
    title: '管网数字孪生平台加强工况推演与应急辅助能力',
    source: '能源数字化周刊',
    sourceType: '微信公众号',
    time: '2026-07-30 18:40',
    category: '数字孪生',
    importance: '重点',
    summary: '实时工况、设备状态和地理空间信息被整合到统一场景，用于泄漏影响分析和资源调度推演。',
    tags: ['数字孪生', '工况推演', '应急辅助'],
    body: ['数字孪生应用正从展示走向计算。', '模型校准与实时数据质量决定推演可信度。', '应急场景需建立结果边界和人工确认机制。']
  }
]

export const paperItems = [
  {
    id: 'paper-001',
    title: 'Deep learning for defect identification in long-distance pipelines: A systematic review',
    titleZh: '面向长输管道缺陷识别的深度学习方法系统综述',
    authors: ['Liu Wei', 'Zhang Han', 'Maria Costa'],
    institutions: ['中国石油大学（北京）', 'Pipeline Research Council International'],
    journal: 'Journal of Pipeline Science and Engineering',
    year: 2026,
    doi: '10.1016/j.jpse.2026.104218',
    access: '开放获取',
    citations: 18,
    abstract: '系统梳理视觉、漏磁、超声和声学检测中的深度学习模型，比较数据集规模、泛化能力与可解释性，为工程算法选型提供证据。',
    keywords: ['深度学习', '缺陷识别', '漏磁检测']
  },
  {
    id: 'paper-002',
    title: 'Stress monitoring of buried pipelines based on magnetic anisotropy',
    titleZh: '基于磁各向异性的埋地管道应力监测方法',
    authors: ['Wang Qiang', 'Chen Rui'],
    institutions: ['国家管网集团研究总院'],
    journal: 'NDT & E International',
    year: 2025,
    doi: '10.1016/j.ndteint.2025.103102',
    access: '仅元数据',
    citations: 12,
    abstract: '研究磁信号与轴向应力变化的关联特征，提出适用于现场条件的温度补偿和基线校准方法。',
    keywords: ['磁各向异性', '应力监测', '温度补偿']
  },
  {
    id: 'paper-003',
    title: 'Multi-source data fusion for pipeline integrity assessment',
    titleZh: '面向管道完整性评价的多源数据融合框架',
    authors: ['Emily Brown', 'Li Ming'],
    institutions: ['University of Alberta', '西南石油大学'],
    journal: 'Reliability Engineering & System Safety',
    year: 2025,
    doi: '10.1016/j.ress.2025.110455',
    access: '用户上传',
    citations: 31,
    abstract: '将检测、工况、环境和失效历史纳入概率图模型，实现风险评分不确定性的显式表达。',
    keywords: ['数据融合', '完整性评价', '概率图模型']
  },
  {
    id: 'paper-004',
    title: 'Digital twins for natural gas transmission networks',
    titleZh: '天然气长输管网数字孪生技术与应用',
    authors: ['José Martínez', 'Sun Yi'],
    institutions: ['Technical University of Madrid'],
    journal: 'Applied Energy',
    year: 2024,
    doi: '10.1016/j.apenergy.2024.122908',
    access: '访问受限',
    citations: 47,
    abstract: '总结管网数字孪生的模型同步、状态估计和泄漏推演方法，并讨论实时性与模型可信度。',
    keywords: ['数字孪生', '状态估计', '天然气管网']
  }
]

export const knowledgeDocuments = [
  { id: 'doc-001', name: '津华管道多元检测数据缺陷智能化分析算法及应用', type: '内部文献', format: 'DOCX', pages: 68, owner: '科研团队', permission: '仅自己可见', status: '已解析', updatedAt: '2026-08-03', summary: '项目技术路线、数据治理方案、算法验证指标与工程应用计划。', tags: ['多元检测', '缺陷识别'] },
  { id: 'doc-002', name: '基于磁各向异性原理的管道本体应力监测技术研究', type: '历史项目', format: 'PDF', pages: 112, owner: '科研管理部', permission: '项目组可见', status: '已解析', updatedAt: '2026-08-01', summary: '应力监测原理、试验设计、现场标定和工程示范结果。', tags: ['应力监测', '磁各向异性'] },
  { id: 'doc-003', name: 'Pipeline Integrity Management Recommended Practice 2026', type: '英文报告', format: 'PDF', pages: 184, owner: '情报分析组', permission: '全员可见', status: '已解析', updatedAt: '2026-07-29', summary: '国际管道完整性管理推荐实践与典型失效案例。', tags: ['完整性管理', '国际标准'] },
  { id: 'doc-004', name: '科技项目需求填报表模板（2026版）', type: '模板', format: 'DOCX', pages: 16, owner: '科研管理部', permission: '全员可见', status: '已解析', updatedAt: '2026-07-25', summary: '包括封面字段、需求背景、研究内容、技术指标与预算表。', tags: ['项目申报', '模板'] },
  { id: 'doc-005', name: '华北区域第三方施工风险事件汇编', type: '其他', format: 'XLSX', pages: 32, owner: '安全运行部', permission: '受限', status: '解析中', updatedAt: '2026-07-22', summary: '近三年第三方施工风险事件及处置结果汇编。', tags: ['第三方施工', '案例'] }
]

export const researchReports = [
  { id: 'report-001', title: '多元检测数据缺陷智能化分析技术路线报告', type: '技术路线报告', status: '待修改', version: 'V1.3', progress: 100, updatedAt: '今天 10:24', words: 12680 },
  { id: 'report-002', title: '管道本体应力监测科研需求报告', type: '科研需求报告', status: '生成中', version: 'V0.8', progress: 68, updatedAt: '今天 09:42', words: 8240 },
  { id: 'report-003', title: '智能阴保监测科技项目需求填报表', type: '科技项目需求填报表', status: '已完成', version: 'V2.0', progress: 100, updatedAt: '昨天 16:20', words: 9380 },
  { id: 'report-004', title: '高后果区风险动态评价研究综述', type: '研究综述', status: '草稿', version: 'V0.2', progress: 12, updatedAt: '07-30 14:08', words: 1680 }
]

export const recentTasks = [
  { id: 'task-001', title: '管道本体应力监测科研需求报告', type: '科研生成', status: 'generating', statusLabel: '章节生成', progress: 68, updatedAt: '2 分钟前' },
  { id: 'task-002', title: '管网科技情报日报 · 8月4日', type: '日报生成', status: 'completed', statusLabel: '已完成', progress: 100, updatedAt: '18 分钟前' },
  { id: 'task-003', title: '国际完整性管理实践报告解析', type: '资料解析', status: 'retrieving', statusLabel: '向量索引', progress: 82, updatedAt: '31 分钟前' },
  { id: 'task-004', title: '智能阴保项目填报表导出', type: '文档导出', status: 'completed', statusLabel: '已完成', progress: 100, updatedAt: '昨天' }
]

export const digestReports = [
  { id: 'digest-001', title: '管网科技情报日报 · 2026年8月4日', type: '日报', period: '2026-08-04', sources: 18, status: '已完成', version: 'V1.0', updatedAt: '今天 10:16' },
  { id: 'digest-002', title: '管道检测与完整性技术周报 · 第31周', type: '周报', period: '07-27 至 08-02', sources: 63, status: '待审核', version: 'V1.2', updatedAt: '昨天 17:40' },
  { id: 'digest-003', title: '应力监测专题月报 · 2026年7月', type: '月报', period: '2026-07-01 至 2026-07-31', sources: 27, status: '草稿', version: 'V0.4', updatedAt: '07-31 11:20' },
  { id: 'digest-004', title: '智能阴保情报自动简报', type: '自动任务', period: '每周一 09:00', sources: 16, status: '运行中', version: '计划', updatedAt: '07-29 09:00' }
]

export const reportTemplates = [
  { id: 'template-01', name: '科技项目需求填报表', description: '结构化封面、需求背景、技术指标与经费预算', color: '#2764e7' },
  { id: 'template-02', name: '科研需求报告', description: '问题分析、研究目标、研究内容、考核指标', color: '#0b8f87' },
  { id: 'template-03', name: '技术路线报告', description: '现状评估、技术路线、试验验证与实施计划', color: '#7357c8' }
]

export const taskStages = ['资料校验', '文件解析', '证据检索', '大纲规划', '章节生成', '引用校验', '质量检查', '图形生成', '导出准备']

export function findNews(id) {
  return newsItems.find(item => item.id === id) || newsItems[0]
}

export function findPaper(id) {
  return paperItems.find(item => item.id === id) || paperItems[0]
}

export function findDocument(id) {
  return knowledgeDocuments.find(item => item.id === id) || knowledgeDocuments[0]
}

export function findReport(id) {
  return researchReports.find(item => item.id === id) || researchReports[0]
}

export function findDigest(id) {
  return digestReports.find(item => item.id === id) || digestReports[0]
}
