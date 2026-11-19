import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function interceptors() {
  let success, failure
  const service = { interceptors: {
    request: { use() {} },
    response: { use(yes, no) { success = yes; failure = no } }
  } }
  const axios = { defaults: { headers: {} }, create: () => service }
  const source = readFileSync(new URL('../src/utils/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '')
    .replaceAll('import.meta.env', '({ VITE_APP_BASE_API: "/api" })')
    .replaceAll('export function', 'function').replaceAll('export let', 'let')
    .replace('export default service', 'return service')
  new Function('axios', 'decryptTransportResponse', 'decryptTransportErrorResponse', 'shouldRetryTransportWithFreshKey',
    'ElMessage', 'errorCode', 'console', source)(axios, async value => value, async value => value, () => false,
    () => {}, {}, { log() {} })
  return { success, failure }
}

test('business errors retain the screening recovery signal after transport decryption', async () => {
  const { success, failure } = interceptors()
  const payload = { code: 500, msg: '筛选结果已过期', data: 'digest_screening_restart' }
  const isRecoverable = error => error instanceof Error && error.message === payload.msg && error.data === payload.data && error.code === 500
  await assert.rejects(success({ data: payload, request: {} }), isRecoverable)
  await assert.rejects(failure({ response: { status: 400, data: payload } }), isRecoverable)
})

test('a temporary model error remains a retryable message without invalidating its receipt', async () => {
  const { success } = interceptors()
  await assert.rejects(success({ data: { code: 500, msg: '模型服务暂时不可用', data: null }, request: {} }), error =>
    error.message === '模型服务暂时不可用' && error.data === null)
})
