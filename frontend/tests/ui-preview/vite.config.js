import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import baseConfig from '../../vite.config.js'

const frontend = fileURLToPath(new URL('../../', import.meta.url))
const apiPath = `${frontend}src/api/pipeline/intelligence.js`
const exports = [...readFileSync(apiPath, 'utf8').matchAll(/export (?:async )?function (\w+)/g)].map(match => match[1])
const extraApis = {
  '@/api/ai/model': ['listModel', 'listModelAll', 'getModel', 'addModel', 'updateModel', 'delModel', 'testModel'],
  '@/api/pipeline/categories': ['listPipelineCategories', 'createPipelineCategory', 'updatePipelineCategory', 'deletePipelineCategory']
}
const base = baseConfig({ mode: 'ui-preview', command: 'serve' })

// 独立、仅监听本机的合成数据环境，不加载 permission.js，不连接业务接口。
// 生产入口及其认证/授权行为不受此配置影响。
export default {
  ...base,
  root: fileURLToPath(new URL('./', import.meta.url)),
  publicDir: `${frontend}public`,
  define: { ...base.define, 'import.meta.env.VITE_PORTAL_DEMO_DATA': JSON.stringify('true') },
  plugins: [
    {
      name: 'ui-preview-fixture-api', enforce: 'pre',
      resolveId(id) {
        if (id === '@/api/pipeline/intelligence' || id === apiPath || id === apiPath.slice(0, -3)) return '\0ui-preview-api'
        for (const key of Object.keys(extraApis)) if (id === key || id === `${frontend}src/${key.slice(2)}.js` || id === `${frontend}src/${key.slice(2)}`) return `\0ui-preview-extra:${key}`
      },
      load(id) {
        if (id !== '\0ui-preview-api' && !id.startsWith('\0ui-preview-extra:')) return
        const fixtureModule = JSON.stringify(new URL('./fixtures.js', import.meta.url).href)
        const names = id === '\0ui-preview-api' ? exports : extraApis[id.slice('\0ui-preview-extra:'.length)]
        return `import { fixtureRequest } from ${fixtureModule};\n` + names.map(name => `export const ${name} = (...args) => fixtureRequest('${name}', args);`).join('\n')
      }
    },
    ...base.plugins
  ],
  server: { host: '127.0.0.1', port: 12581, strictPort: true, open: false, fs: { allow: [frontend] } }
}
