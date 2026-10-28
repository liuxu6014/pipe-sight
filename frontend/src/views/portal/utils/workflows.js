const workflows = [
  { path: '/portal/news', title: '资讯', steps: ['按关键词、来源和分类筛选资讯', '打开详情，区分原文与系统分析', '加入资料库，继续报告选材'] },
  { path: '/portal/papers', title: '论文', steps: ['查询题名、DOI或发表年份', '核对元数据、摘要及全文访问范围', '复制引用或加入资料库'] },
  { path: '/portal/knowledge', title: '研究资料', steps: ['查阅授权资料或上传本人文件', '等待安全检查及解析，核对正文位置', '确认用途授权后加入资料库'] },
  { path: '/portal/research', title: '科研报告', steps: ['选择已发布模板与授权证据', '填写业务需求，确认章节大纲', '提交后台任务，按真实状态跟踪', '编辑核对引用，复核后按条件导出'] },
  { path: '/portal/digests', title: '情报简报', steps: ['选择覆盖周期、方向与来源', '核对候选和栏目，提交生成', '编辑并核对原文，复核后导出', '自动计划在独立列表查看派发结果'] },
  { path: '/portal/me', title: '个人中心', target: '/portal/me/reports', steps: ['查看报告生成进度与结果', '按类型与状态找到本人记录', '进入对应业务页面继续处理'] },
  { path: '/portal/search', title: '资料检索', steps: ['输入关键词并选择资料类型', '按来源或时间缩小结果范围', '打开原始对象，核验后再选材'] }
]

export function getPortalWorkflow(path = '') {
  return workflows.find(item => path === item.path || path.startsWith(item.path + '/')) || null
}
