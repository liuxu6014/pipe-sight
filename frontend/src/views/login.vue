<template>
  <div class="pipeline-user-login calm-login-page calm-homepage-auth" :class="{ 'is-login-open': loginVisible }">
    <section class="calm-photo-hero pipechina-photo-hero" aria-label="平台登录封面">
      <img class="calm-hero-photo" :src="CALM_MOUNTAIN_LAKE_URL" alt="国家管网输气站场背景" />
      <div class="calm-hero-shade" aria-hidden="true"></div>
      <div class="calm-hero-fade" aria-hidden="true"></div>

      <nav class="calm-login-nav" aria-label="平台登录导航">
        <div class="calm-nav-left">
          <button class="calm-brand" type="button" @click="selectDestination('/portal')">
            <img class="calm-brand-logo" :src="PIPECHINA_LOGO_URL" :data-source="PIPECHINA_LOGO_SOURCE_URL" alt="国家管网标识" />
          </button>

        </div>

      </nav>
    </section>

    <main class="calm-start-panel">
      <section class="calm-start-copy" aria-labelledby="calm-login-title">
        <h1 id="calm-login-title">连接信息，支撑科研决策。</h1>
        <p>面向管网科技情报发现、证据沉淀与研究成果生成。</p>

        <div class="calm-start-actions">
          <button class="calm-start-primary" type="button" @click="startTrial">
            进入平台
          </button>
        </div>

        <div class="calm-value-grid" aria-label="平台能力">
          <button v-for="item in portalDestinations" :key="`value-${item.path}`" type="button" @click="selectDestination(item.path)">
            <span>{{ item.order }}</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.description }}</small>
          </button>
        </div>
      </section>
    </main>

    <Transition name="calm-modal">
      <div
        v-if="loginVisible"
        class="calm-login-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="calm-login-card-title"
        @click.self="closeLogin"
        @keydown="handleDialogKeydown"
      >
        <div class="calm-modal-backdrop" aria-hidden="true" @click="closeLogin"></div>

        <section ref="loginCardRef" class="calm-login-dialog" tabindex="-1" :aria-busy="loading">
          <div class="calm-login-card calm-login-sheet">
            <button class="calm-modal-close" type="button" aria-label="关闭登录窗口" @click="closeLogin">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
                <path d="M6 6l12 12" />
                <path d="M18 6L6 18" />
              </svg>
            </button>

            <div class="calm-compact-auth">
              <div class="calm-auth-brand-row">
                <img class="calm-brand-logo compact" :src="PIPECHINA_LOGO_URL" :data-source="PIPECHINA_LOGO_SOURCE_URL" alt="国家管网标识" />
                <span>
                  <strong>{{ PLATFORM_NAME }}</strong>
                </span>
              </div>

              <div class="login-card-head">
                <h2 id="calm-login-card-title">登录</h2>
                <p>继续访问{{ selectedDestinationLabel }}</p>
              </div>

              <el-form
                ref="loginRef"
                :model="loginForm"
                :rules="loginRules"
                class="calm-form"
                @keyup.enter="handleLogin"
              >
                <el-form-item prop="username" class="calm-form-item">
                  <label for="login-username">账号</label>
                  <el-input
                    id="login-username"
                    v-model="loginForm.username"
                    size="large"
                    autocomplete="username"
                    placeholder="请输入账号"
                  >
                    <template #prefix>
                      <svg viewBox="0 0 24 24" class="input-icon" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
                        <circle cx="12" cy="8" r="4" />
                        <path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
                      </svg>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item prop="password" class="calm-form-item">
                  <label for="login-password">密码</label>
                  <el-input
                    id="login-password"
                    v-model="loginForm.password"
                    size="large"
                    type="password"
                    autocomplete="current-password"
                    placeholder="请输入密码"
                    show-password
                  >
                    <template #prefix>
                      <svg viewBox="0 0 24 24" class="input-icon" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
                        <rect x="3" y="11" width="18" height="11" rx="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item v-if="captchaEnabled" prop="code" class="calm-form-item calm-form-code">
                  <label for="login-code">验证码</label>
                  <div class="calm-code-row">
                    <el-input
                      id="login-code"
                      v-model="loginForm.code"
                      size="large"
                      autocomplete="off"
                      placeholder="请输入验证码"
                    >
                      <template #prefix>
                        <svg viewBox="0 0 24 24" class="input-icon" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
                          <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2v-4M9 21H5a2 2 0 0 1-2-2v-4m0-4h18" />
                        </svg>
                      </template>
                    </el-input>
                    <button type="button" class="calm-code-img" aria-label="刷新验证码" @click="getCode">
                      <img v-if="codeUrl" :src="codeUrl" alt="验证码图片" @error="handleCodeImageError" />
                      <span v-else class="calm-code-error">验证码加载失败<br />点击刷新</span>
                    </button>
                  </div>
                </el-form-item>

                <div class="calm-form-options">
                  <el-checkbox v-model="loginForm.rememberMe">记住账号</el-checkbox>
                  <router-link v-if="register" to="/register" class="register-link">注册账号</router-link>
                </div>

                <button class="calm-submit" type="button" :disabled="loading" @click.prevent="handleLogin">
                  <span>{{ loading ? '验证中...' : (loginAuthenticated ? '重试进入' : '登 录') }}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true">
                    <path d="M5 12h14" />
                    <path d="m13 6 6 6-6 6" />
                  </svg>
                </button>
              </el-form>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Cookies from 'js-cookie'
import { ElMessage } from 'element-plus'
import { getCodeImg } from '@/api/login'
import useUserStore from '@/store/modules/user'
import usePermissionStore from '@/store/modules/permission'
import { resolvePostLoginPath } from '@/utils/portal/auth'
import { isHttp } from '@/utils/validate'
import pipechinaEmblemUrl from '@/assets/logo/pipechina-emblem.png'
import pipechinaLoginBackgroundUrl from '@/assets/images/pipechina-login-background.jpg'

defineOptions({ name: 'UnifiedPlatformLogin' })

const CALM_MOUNTAIN_LAKE_URL = pipechinaLoginBackgroundUrl
const PIPECHINA_LOGO_SOURCE_URL = 'https://www.pipechina.com.cn/Uploads/Picture/2023/09/05/s64f6d50827d73.png'
const PIPECHINA_LOGO_URL = pipechinaEmblemUrl
const PLATFORM_NAME = import.meta.env.VITE_APP_TITLE || '国家管网科技情报与科研辅助平台'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const loginRef = ref()
const loginCardRef = ref()
const loginTrigger = ref(null)
const bodyOverflowBeforeModal = ref('')
const loading = ref(false)
const loginAuthenticated = ref(false)
const loginVisible = ref(false)
const captchaEnabled = ref(true)
const register = ref(false)
const codeUrl = ref('')
const redirect = ref(undefined)
const loginForm = ref({
  username: '',
  password: '',
  rememberMe: false,
  code: '',
  uuid: ''
})

const portalDestinations = [
  {
    order: '01',
    title: '新闻资讯',
    path: '/portal/news',
    description: '追踪行业动态与技术线索'
  },
  {
    order: '02',
    title: '论文资料',
    path: '/portal/papers',
    description: '检索论文元数据与可信引用'
  },
  {
    order: '03',
    title: '科研生成',
    path: '/portal/research',
    description: '从授权证据生成研究成果'
  },
  {
    order: '04',
    title: '情报简报',
    path: '/portal/digests',
    description: '汇总周期情报与热点研判'
  }
]

const loginRules = {
  username: [{ required: true, trigger: 'blur', message: '请输入您的账号' }],
  password: [{ required: true, trigger: 'blur', message: '请输入您的密码' }],
  code: [{ required: true, trigger: 'change', message: '请输入验证码' }]
}

const activeDestination = computed(() => {
  const target = redirect.value || '/portal'
  const matched = portalDestinations.find(item => target === item.path || target.startsWith(`${item.path}/`))
  return matched?.path || '/portal'
})

const selectedDestinationLabel = computed(() => {
  const matched = portalDestinations.find(item => activeDestination.value === item.path)
  return matched?.title || '平台工作台'
})

watch(route, newRoute => {
  redirect.value = normalizeRedirect(newRoute.query?.redirect)
}, { immediate: true })

watch(loginVisible, visible => {
  if (visible) {
    bodyOverflowBeforeModal.value = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    nextTick(() => document.getElementById('login-username')?.focus())
  } else {
    document.body.style.overflow = bodyOverflowBeforeModal.value
    nextTick(() => loginTrigger.value?.focus?.())
  }
})

function normalizeRedirect(value) {
  return Array.isArray(value) ? value[0] : value
}

function selectDestination(path) {
  redirect.value = path
  revealLogin()
}

function startTrial() {
  redirect.value = redirect.value || '/portal'
  revealLogin()
}

function revealLogin() {
  if (!loginVisible.value) {
    loginTrigger.value = document.activeElement
    getCode()
  }
  loginVisible.value = true
}

function closeLogin() {
  loginVisible.value = false
}

function handleDialogKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeLogin()
    return
  }
  if (event.key !== 'Tab' || !loginCardRef.value) return
  const focusable = Array.from(loginCardRef.value.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )).filter(element => element.offsetParent !== null && element.getAttribute('aria-hidden') !== 'true')
  if (!focusable.length) {
    event.preventDefault()
    loginCardRef.value.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || !loginCardRef.value.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function handleLogin() {
  if (loading.value) return
  const submit = () => {
    loading.value = true
    Cookies.remove('password')
    if (loginForm.value.rememberMe) {
      Cookies.set('username', loginForm.value.username, { expires: 30 })
      Cookies.set('rememberMe', 'true', { expires: 30 })
    } else {
      Cookies.remove('username')
      Cookies.remove('rememberMe')
    }

    const authentication = loginAuthenticated.value ? Promise.resolve() : userStore.login(loginForm.value)
    authentication.then(async () => {
      loginAuthenticated.value = true
      const query = route.query || {}
      const otherQueryParams = Object.keys(query).reduce((acc, cur) => {
        if (cur !== 'redirect') {
          acc[cur] = query[cur]
        }
        return acc
      }, {})
      const targetPath = await resolvePostLoginTarget(redirect.value)
      const destination = router.resolve(targetPath)
      await router.push({ path: destination.path, query: { ...destination.query, ...otherQueryParams }, hash: destination.hash })
    }).catch(error => {
      if (loginAuthenticated.value) {
        ElMessage.error('登录成功，但用户信息或菜单加载失败，请重试')
      } else {
        ElMessage.error(error?.message || '登录失败，请检查账号、密码或验证码')
        loginForm.value.password = ''
        loginForm.value.code = ''
        if (captchaEnabled.value) getCode()
      }
    }).finally(() => {
      loading.value = false
    })
  }
  // 登录后的加载失败只重试用户信息和菜单，不重复提交已消费的验证码。
  if (loginAuthenticated.value) {
    submit()
  } else {
    loginRef.value.validate(valid => { if (valid) submit() })
  }
}

async function resolvePostLoginTarget(requestedPath) {
  await userStore.getInfo()
  const accessRoutes = await permissionStore.generateRoutes(userStore)
  accessRoutes.forEach(route => {
    if (!isHttp(route.path)) {
      router.addRoute(route)
    }
  })

  return resolvePostLoginPath(userStore, requestedPath)
}

function getCode() {
  codeUrl.value = ''
  loginForm.value.code = ''
  loginForm.value.uuid = ''
  getCodeImg().then(res => {
    captchaEnabled.value = res.captchaEnabled === undefined ? true : res.captchaEnabled
    register.value = res.registerEnabled === undefined ? false : res.registerEnabled
    if (captchaEnabled.value) {
      codeUrl.value = 'data:image/png;base64,' + res.img
      loginForm.value.uuid = res.uuid
    }
  }).catch(() => {
    captchaEnabled.value = true
    ElMessage.warning('验证码暂时无法加载，请稍后重试')
  })
}

function handleCodeImageError() {
  codeUrl.value = ''
  loginForm.value.uuid = ''
}

function getCookie() {
  const rememberMe = Cookies.get('rememberMe') === 'true'
  const username = rememberMe ? Cookies.get('username') || '' : ''
  Cookies.remove('password')
  if (!rememberMe) {
    Cookies.remove('username')
    Cookies.remove('rememberMe')
  }
  loginForm.value = {
    ...loginForm.value,
    username,
    password: '',
    rememberMe
  }
}

getCode()
getCookie()

onBeforeUnmount(() => {
  document.body.style.overflow = bodyOverflowBeforeModal.value
})
</script>

<style lang="scss" scoped>
.pipeline-user-login.calm-login-page.calm-homepage-auth {
  min-height: 100dvh;
  overflow-x: hidden;
  background: #f6f6f6;
  color: #172233;
}

.calm-photo-hero {
  position: relative;
  height: clamp(270px, 43vh, 430px);
  overflow: hidden;
}

.calm-hero-photo {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  display: block;
}

.calm-hero-shade,
.calm-hero-fade {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.calm-hero-shade {
  background:
    linear-gradient(180deg, rgba(11, 32, 50, 0.38), rgba(11, 32, 50, 0.08) 52%, rgba(246, 246, 246, 0) 100%),
    linear-gradient(90deg, rgba(7, 32, 52, 0.28), rgba(7, 32, 52, 0));
}

.calm-hero-fade {
  top: auto;
  height: 260px;
  background: linear-gradient(180deg, rgba(246, 246, 246, 0), #f6f6f6);
}

.pipechina-photo-hero .calm-hero-fade {
  height: 72px;
  background: linear-gradient(180deg, rgba(246, 246, 246, 0), rgba(246, 246, 246, 0.78) 82%, #f6f6f6);
}

.calm-login-nav {
  position: absolute;
  z-index: 5;
  top: 22px;
  left: 36px;
  right: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
}

.calm-nav-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.calm-brand,
.calm-nav-link,
.calm-start-primary,
.calm-start-secondary,
.calm-code-img,
.calm-submit,
.calm-modal-close {
  cursor: pointer;
}

.calm-brand {
  width: 86px;
  height: 72px;
  border: 0;
  background: transparent;
  box-shadow: none;
  overflow: hidden;
  padding: 0;
}

.calm-brand-logo {
  width: 86px;
  height: 72px;
  display: block;
  background: transparent;
  object-fit: contain;
  object-position: left center;

  &.compact {
    width: 62px;
    height: 52px;
    border: 0;
    background: transparent;
    object-fit: contain;
  }
}

.calm-nav-link {
  min-height: 38px;
  border: 1px solid rgba(255, 255, 255, 0.36);
  border-radius: 999px;
  color: #fff;
  background: rgba(7, 32, 52, 0.16);
  backdrop-filter: blur(8px);
  padding: 0 18px;
  font-size: 14px;
  transition: background 0.2s ease, border-color 0.2s ease;

  &:hover {
    border-color: rgba(255, 255, 255, 0.62);
    background: rgba(7, 32, 52, 0.28);
  }
}

.calm-start-primary,
.calm-submit {
  border-color: transparent;
  background: linear-gradient(135deg, #2d9bea, #6366f1);
}

.calm-start-panel {
  position: relative;
  z-index: 4;
  margin-top: -88px;
  padding: 132px 24px 42px;
  background: linear-gradient(180deg, rgba(246, 246, 246, 0) 0, #f6f6f6 172px, #f6f6f6 100%);
}

.calm-start-copy {
  width: min(100%, 1040px);
  margin: 0 auto;
  text-align: center;
}

.calm-start-copy h1 {
  max-width: 620px;
  margin: 0 auto;
  color: #182c3d;
  font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
  font-size: clamp(30px, 3.4vw, 42px);
  font-weight: 700;
  line-height: 1.18;
  overflow-wrap: anywhere;
}

.calm-start-copy p {
  max-width: 460px;
  margin: 10px auto 0;
  color: #667789;
  font-size: 15px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.calm-start-actions {
  display: flex;
  justify-content: center;
  gap: 14px;
  margin-top: 18px;
}

.calm-start-primary,
.calm-start-secondary {
  min-width: 152px;
  min-height: 46px;
  border-radius: 999px;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 700;
}

.calm-start-primary {
  border: 0;
  color: #fff;
  box-shadow: 0 12px 30px rgba(45, 155, 234, 0.26);
}

.calm-start-secondary {
  border: 1px solid #d4dee8;
  color: #365167;
  background: rgba(255, 255, 255, 0.78);
}

.calm-value-grid {
  margin-top: 32px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  text-align: left;
}

.calm-value-grid button {
  min-height: 108px;
  padding: 16px 18px;
  border: 1px solid rgba(202, 214, 226, 0.9);
  border-radius: 14px;
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.82);
  color: #183044;
  cursor: pointer;
  box-shadow: 0 10px 30px rgba(31, 57, 81, 0.06);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.calm-value-grid button:hover,
.calm-value-grid button:focus-visible {
  border-color: rgba(45, 155, 234, 0.52);
  box-shadow: 0 16px 38px rgba(31, 57, 81, 0.12);
  outline: none;
  transform: translateY(-3px);
}

.calm-value-grid button > span {
  color: #2d9bea;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.calm-value-grid button > strong {
  margin-top: 12px;
  font-size: 16px;
}

.calm-value-grid button > small {
  margin-top: 7px;
  color: #718294;
  font-size: 12px;
  line-height: 1.6;
}

.calm-login-modal {
  position: fixed;
  z-index: 20;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
}

.calm-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(10, 28, 44, 0.32);
  backdrop-filter: blur(10px);
}

.calm-login-dialog {
  position: relative;
  z-index: 1;
  width: min(430px, 100%);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  border-radius: 16px;
}

.calm-login-card.calm-login-sheet {
  position: relative;
  padding: 32px 28px 26px;
  border: 1px solid rgba(255, 255, 255, 0.74);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 70px rgba(14, 42, 66, 0.2);
}

.calm-modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 999px;
  color: #6f8294;
  background: rgba(239, 244, 248, 0.9);
  display: grid;
  place-items: center;

  svg {
    width: 18px;
    height: 18px;
  }
}

.calm-auth-brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-right: 44px;

  span {
    display: grid;
    gap: 4px;
  }

  strong {
    color: #163047;
    font-size: 16px;
    line-height: 1.35;
  }

  small {
    color: #718497;
    font-size: 12px;
  }
}

.login-card-head {
  margin-top: 24px;
  padding-right: 44px;

  h2 {
    margin: 0;
    color: #102b42;
    font-size: 24px;
    line-height: 1.25;
  }

  p {
    margin: 8px 0 0;
    color: #708394;
    font-size: 13px;
  }
}

.calm-form {
  margin-top: 24px;

  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  label {
    display: block;
    margin-bottom: 8px;
    color: #30495f;
    font-size: 13px;
    font-weight: 700;
  }

  :deep(.el-input__wrapper) {
    border-radius: 10px;
    box-shadow: 0 0 0 1px #cbd9e3 inset;
    transition: box-shadow 0.2s ease;
  }

  :deep(.el-input__wrapper:hover) {
    box-shadow: 0 0 0 1px #9fb8ca inset;
  }

  :deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 0 0 2px rgba(45, 155, 234, 0.24) inset;
  }

  .input-icon {
    width: 18px;
    height: 18px;
    color: #879aac;
  }
}

.calm-code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 122px;
  gap: 12px;
}

.calm-code-img {
  height: 42px;
  overflow: hidden;
  border: 1px solid #d3dde6;
  border-radius: 10px;
  background: #f8fafc;
  padding: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.calm-code-error {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  color: #9a6a32;
  font-size: 12px;
  line-height: 1.35;
  text-align: center;
}

.calm-form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 0 22px;

  :deep(.el-checkbox__label) {
    color: #52687a;
    font-size: 13px;
  }
}

.register-link {
  color: #005487;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.calm-submit {
  width: 100%;
  min-height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 0;
  border-radius: 999px;
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 12px 28px rgba(45, 155, 234, 0.26);

  &:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }

  svg {
    width: 18px;
    height: 18px;
  }
}

.calm-modal-enter-active,
.calm-modal-leave-active {
  transition: opacity 0.2s ease;
}

.calm-modal-enter-from,
.calm-modal-leave-to {
  opacity: 0;
}

.calm-modal-enter-active .calm-login-dialog,
.calm-modal-leave-active .calm-login-dialog {
  transition: transform 0.2s ease;
}

.calm-modal-enter-from .calm-login-dialog,
.calm-modal-leave-to .calm-login-dialog {
  transform: translateY(10px);
}

@media (max-width: 760px) {
  .calm-login-nav {
    top: 14px;
    left: 16px;
    right: 16px;
    gap: 12px;
  }

  .calm-nav-left {
    gap: 8px;
  }

  .calm-nav-left .calm-nav-link {
    display: none;
  }

  .calm-nav-link {
    min-height: 34px;
    padding: 0 13px;
    font-size: 13px;
  }

  .calm-photo-hero {
    height: 180px;
  }

  .pipechina-photo-hero .calm-hero-fade {
    height: 54px;
  }

  .calm-start-panel {
    margin-top: -50px;
    padding: 82px 16px 32px;
  }

  .calm-start-copy {
    width: min(100%, 360px);
    margin: 0 auto;
  }

  .calm-start-copy h1 {
    max-width: 360px;
    margin: 0 auto;
    font-size: clamp(25px, 6.8vw, 29px);
  }

  .calm-start-copy p {
    max-width: 280px;
    margin: 14px auto 0;
    font-size: 15px;
  }

  .calm-start-actions {
    align-items: stretch;
    gap: 10px;
    margin-top: 16px;
  }

  .calm-value-grid {
    margin-top: 24px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .calm-value-grid button {
    min-height: 96px;
    padding: 12px;
  }

  .calm-value-grid button > strong {
    margin-top: 8px;
    font-size: 14px;
  }

  .calm-value-grid button > small {
    font-size: 11px;
    line-height: 1.45;
  }

  .calm-start-primary,
  .calm-start-secondary {
    min-width: 0;
    width: auto;
    flex: 1;
  }

  .calm-login-modal {
    padding: 12px;
  }

  .calm-login-dialog {
    max-height: calc(100vh - 24px);
    border-radius: 12px;
  }

  .calm-login-card.calm-login-sheet {
    padding: 28px 18px 20px;
    border-radius: 12px;
  }

  .calm-modal-close {
    top: 12px;
    right: 12px;
  }

  .calm-auth-brand-row,
  .login-card-head {
    padding-right: 42px;
  }

  .calm-code-row {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .calm-nav-link,
  .calm-start-primary,
  .calm-start-secondary,
  .calm-code-img,
  .calm-submit,
  .calm-modal-close {
    transition: none;
  }

  .calm-modal-enter-active,
  .calm-modal-leave-active,
  .calm-modal-enter-active .calm-login-dialog,
  .calm-modal-leave-active .calm-login-dialog {
    transition: none;
  }

  .calm-modal-enter-from .calm-login-dialog,
  .calm-modal-leave-to .calm-login-dialog {
    transform: none;
  }
}
</style>
