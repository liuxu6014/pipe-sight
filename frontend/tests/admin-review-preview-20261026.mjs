// Isolated component preview for this admin review. All API boundaries are fixtures.
// Run: node tests/admin-review-preview-20261026.mjs
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const mocks = `
const allJobs = Array.from({length:73}, (_, i) => ({job_id:String(i+1),topic:'监测论文 '+(i+1),status:i%2?'completed':'failed',progress_pct:100,content:'草稿'}));
export const checkPermi = () => true;
export const listModelAll = async () => ({data:[]});
export const listPipelineTemplates = async () => ({data:{rows:[{id:'17',name:'章节测试模板',purpose:'research',prompt:'提示词',description:'停用模型仍可停用',isEnabled:true,modelId:'8',sections:[{id:'1',title:'技术路线与研究方法',words:1000,required:true}]}]}});
export const getPipelineDashboard = async () => ({data:{metrics:[{label:'新闻资讯',value:180,unit:'条'}],hot_topics:[],collect_status:[{id:'12',name:'科技来源',status:'success',fetched_count:180,saved_count:150,failed_count:0},{id:'13',name:'科技来源',status:'success',fetched_count:0,saved_count:0,failed_count:0}]}});
export const listPipelineKnowledgeDocuments = async () => ({data:{rows:[{id:'54',name:'排队资料.pdf',parseStatus:'queued',status:'等待解析',permission:'仅自己可见',canManage:true,fileSize:1024}]}});
export const listPipelineAdminReports = async () => ({data:{rows:[],total:0}});
export const getPipelineIntelligenceDetail = async () => ({data:{title:'情报示例',category:'paper',category_name:'检测技术',abstract:'真实摘要',tags:[],source:'科技来源',publish_time:'2026-10-26'}});
export const listManuscriptJobs = async q => { const rows=allJobs.filter(x=>(!q.keyword||x.topic.includes(q.keyword))&&(!q.status||x.status===q.status)); return {data:{rows:rows.slice((q.pageNum-1)*q.pageSize,q.pageNum*q.pageSize),total:rows.length}} };
export const getManuscriptJob = async id => ({data:allJobs.find(x=>x.job_id===id)});
export const createPipelineTemplate = async () => {throw Error('preview: writes disabled')};
export const updatePipelineTemplate = createPipelineTemplate, retirePipelineTemplate = createPipelineTemplate,
deletePipelineKnowledgeDocument = createPipelineTemplate, downloadPipelineKnowledgeDocument = createPipelineTemplate,
reparsePipelineKnowledgeDocument = createPipelineTemplate, uploadPipelineKnowledgeDocument = createPipelineTemplate,
exportPipelineReport = createPipelineTemplate, exportManuscript = createPipelineTemplate,
generateManuscript = createPipelineTemplate, suggestManuscriptTitles = createPipelineTemplate;
`
const entry = `
import {createApp,h} from 'vue';
import {createRouter,createWebHistory,RouterView} from 'vue-router';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
const pages=import.meta.glob('/src/views/pipeline/**/*.vue');
const routes=[['template','template/index'],['knowledge','knowledge/index'],['dashboard','dashboard/index'],['manuscript','manuscript/index'],['detail','intelligence/detail'],['report','report/index']].map(([name,path])=>({path:'/pipeline/'+name,component:pages['/src/views/pipeline/'+path+'.vue']}));
const router=createRouter({history:createWebHistory(),routes});
const app=createApp({render:()=>h(RouterView)}).use(router).use(ElementPlus);
app.directive('hasPermi',{});app.directive('loading',{});app.mount('#app');
`
const server = await createServer({
  configFile: false, root,
  optimizeDeps: { entries: [], include: ['vue', 'vue-router', 'element-plus', '@element-plus/icons-vue'] },
  resolve: { alias: { '@': `${root}src` } },
  plugins: [{
    name: 'admin-review-fixtures', enforce: 'pre',
    resolveId(id) {
      const normalized = id.replace(`${root}src/`, '@/').replace(/\.js$/, '')
      if (['@/api/pipeline/intelligence', '@/api/pipeline/manuscript', '@/api/ai/model', '@/utils/permission'].includes(normalized)) return '\0admin-review-mocks'
      if (id === '/admin-review-entry.js') return '\0admin-review-entry'
    },
    load(id) { if(id==='\0admin-review-mocks') return mocks; if(id==='\0admin-review-entry') return entry },
    configureServer(vite) {
      vite.middlewares.use(async (req,res,next) => {
        if (!req.url.startsWith('/pipeline/')) return next()
        res.setHeader('Content-Type','text/html')
        res.end(await vite.transformIndexHtml(req.url, '<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module" src="/admin-review-entry.js"></script></body></html>'))
      })
    }
  }, vue()],
  server: { host:'127.0.0.1', port:12583, strictPort:true, open:false }
})
await server.listen()
server.printUrls()
