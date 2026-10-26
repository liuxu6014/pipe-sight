import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import baseConfig from '../../vite.config.js'

const frontend = fileURLToPath(new URL('../../', import.meta.url))
const apiPath = `${frontend}src/api/pipeline/intelligence.js`
const exports = [...readFileSync(apiPath, 'utf8').matchAll(/export (?:async )?function (\w+)/g)].map(match => match[1])
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
      resolveId(id) { if (id === '@/api/pipeline/intelligence' || id === apiPath || id === apiPath.slice(0, -3)) return '\0ui-preview-api' },
      load(id) {
        if (id !== '\0ui-preview-api') return
        return `import { fixtureRequest } from '${fileURLToPath(new URL('./fixtures.js', import.meta.url))}';\n` + exports.map(name => `export const ${name} = (...args) => fixtureRequest('${name}', args);`).join('\n')
      }
    },
    ...base.plugins
  ],
  server: { host: '127.0.0.1', port: 12581, strictPort: true, open: false, fs: { allow: [frontend] } }
}
