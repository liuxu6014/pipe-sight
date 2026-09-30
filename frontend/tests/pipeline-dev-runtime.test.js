import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const startScriptPath = new URL('../../start-dev.ps1', import.meta.url)

test('reuses healthy frontend and backend services without creating port races', async () => {
  const script = await readFile(startScriptPath, 'utf8')

  assert.match(script, /\[int\]\$BackendPort = 9099/)
  assert.match(script, /\[int\]\$FrontendPort = 5173/)
  assert.match(script, /SetEnvironmentVariable\('PATH', \$null/)
  assert.match(script, /SetEnvironmentVariable\('Path', \$processPath/)
  assert.match(script, /\$backendBaseUrl = "http:\/\/127\.0\.0\.1:\$BackendPort"/)
  assert.match(script, /function Test-PipeSightBackend/)
  assert.match(script, /'\/pipeline\/workspace'/)
  assert.match(script, /'\/pipeline\/research\/reports\/\{report_id\}\/diagram'/)
  assert.match(script, /'\/pipeline\/research\/reports\/\{report_id\}\/versions\/\{version_no\}\/restore'/)
  assert.match(script, /\$reuseBackend = Test-PipeSightBackend -BaseUrl \$backendBaseUrl/)
  assert.match(script, /Port 9099 is serving an outdated PipeSight API/)
  assert.match(script, /\$frontendBaseUrl = "http:\/\/127\.0\.0\.1:\$FrontendPort"/)
  assert.match(script, /\$reuseFrontend = \$BackendPort -eq 9099 -and \$FrontendPort -eq 5173/)
  assert.match(script, /function Select-AvailableFrontendPort/)
  assert.match(script, /Frontend port \$requestedFrontendPort is occupied; using port \$FrontendPort/)
  assert.match(script, /\$env:VITE_BACKEND_TARGET = \$backendBaseUrl/)
  assert.match(script, /if \(-not \$reuseBackend\) \{[\s\S]*?Starting backend with uv/)
  assert.match(script, /if \(-not \$reuseFrontend\) \{[\s\S]*?Starting frontend with Vite/)
  assert.match(script, /'--port', \[string\]\$FrontendPort/)
})

test('preserves reused service pid files when a newly started peer fails', async () => {
  const script = await readFile(startScriptPath, 'utf8')
  const catchBlock = script.match(/catch \{\s*if \(\$null -ne \$frontendProcess\)[\s\S]*?\s+throw\s*\}/)?.[0] || ''

  assert.match(catchBlock, /if \(\$null -ne \$frontendProcess\)[\s\S]*?Remove-Item -LiteralPath \$FrontendPidFile/)
  assert.match(catchBlock, /if \(\$null -ne \$backendProcess\)[\s\S]*?Remove-Item -LiteralPath \$BackendPidFile/)
  assert.equal((catchBlock.match(/Remove-Item -LiteralPath/g) || []).length, 2)
})
