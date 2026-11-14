<template>
  <div class="ps-page ps-profile-page">
    <PortalPageHeader title="账户设置" />
    <el-skeleton v-if="loading" :rows="6" animated />
    <div v-else-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}</span><el-button @click="loadProfile">重新加载</el-button></div>
    <div v-else class="ps-profile-panel">
      <PortalAvatarEditor :disabled="saving || passwordSaving" @saving="avatarSaving = $event">
        <div class="ps-profile-account">
          <h2>{{ snapshot.nickName || accountName }}</h2>
          <dl>
            <dt>登录账号</dt>
            <dd>{{ accountName }}</dd>
          </dl>
        </div>
      </PortalAvatarEditor>

      <el-form class="ps-profile-form" label-position="left" aria-labelledby="profile-basic-heading" :disabled="accountSaving" @submit.prevent="saveProfile">
        <h2 id="profile-basic-heading">基本资料</h2>
        <div class="ps-profile-fields">
          <el-form-item label="昵称" required><el-input v-model="form.nickName" aria-label="昵称" maxlength="30" autocomplete="nickname" show-word-limit /></el-form-item>
          <el-form-item label="手机号码"><el-input v-model="form.phonenumber" aria-label="手机号码" maxlength="11" inputmode="tel" autocomplete="tel" :prefix-icon="Phone" placeholder="填写手机号码" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="form.email" aria-label="邮箱" maxlength="50" autocomplete="email" :prefix-icon="Message" placeholder="填写常用邮箱" /></el-form-item>
          <el-form-item label="性别"><el-radio-group v-model="form.sex" class="ps-profile-gender" aria-label="性别"><el-radio value="0">男</el-radio><el-radio value="1">女</el-radio><el-radio value="2">不设置</el-radio></el-radio-group></el-form-item>
        </div>
        <p v-if="saveError" class="ps-profile-error" role="alert">{{ saveError }}</p>
        <div class="ps-profile-actions">
          <el-button :disabled="accountSaving || !isDirty" @click="resetProfile">撤销修改</el-button>
          <el-button type="primary" native-type="submit" :disabled="accountSaving || !isDirty" :loading="saving">保存资料</el-button>
          <span v-if="isDirty" class="ps-profile-save-state" role="status">有未保存的修改</span>
        </div>
      </el-form>

      <section class="ps-profile-security" aria-labelledby="profile-security-heading">
        <h2 id="profile-security-heading">账户安全</h2>
        <el-collapse>
          <el-collapse-item name="password" title="修改密码">
            <el-form class="ps-profile-form ps-profile-password-form" label-position="left" aria-label="修改密码" :disabled="accountSaving" @submit.prevent="savePassword">
              <div class="ps-profile-fields">
                <el-form-item label="原密码" required><el-input v-model="password.oldPassword" aria-label="原密码" type="password" autocomplete="current-password" placeholder="请输入当前登录密码" show-password /></el-form-item>
                <el-form-item label="新密码" required><el-input v-model="password.newPassword" aria-label="新密码" type="password" autocomplete="new-password" maxlength="20" placeholder="设置 6–20 个字符的新密码" show-password /></el-form-item>
                <el-form-item label="确认新密码" required><el-input v-model="password.confirmPassword" aria-label="确认新密码" type="password" autocomplete="new-password" maxlength="20" placeholder="再次输入新密码" show-password /></el-form-item>
              </div>
              <p v-if="passwordError" class="ps-profile-error" role="alert">{{ passwordError }}</p>
              <div class="ps-profile-actions">
                <el-button @click="resetPassword">清空输入</el-button>
                <el-button type="primary" native-type="submit" :loading="passwordSaving">修改密码</el-button>
              </div>
            </el-form>
          </el-collapse-item>
        </el-collapse>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Phone, Message } from '@element-plus/icons-vue'
import PortalAvatarEditor from '../components/PortalAvatarEditor.vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import useUserStore from '@/store/modules/user'
import { getUserProfile, updateUserProfile, updateUserPwd } from '@/api/system/user'
import { profileFields, validateProfile, validatePasswordChange } from '@/utils/portal/profile'

const userStore = useUserStore()
const avatarSaving = ref(false)
const loading = ref(true), loadError = ref(''), saveError = ref(''), passwordError = ref('')
const saving = ref(false), passwordSaving = ref(false), accountName = ref('')
const accountSaving = computed(() => saving.value || avatarSaving.value || passwordSaving.value)
const form = reactive(profileFields())
const password = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const snapshot = ref(profileFields())
const isDirty = computed(() => JSON.stringify(profileFields(form)) !== JSON.stringify(snapshot.value))
let active = true, generation = 0
const isCurrent = id => active && String(userStore.id) === id
function resetPassword() {
  Object.assign(password, { oldPassword: '', newPassword: '', confirmPassword: '' })
  passwordError.value = ''
}
function resetProfile() { Object.assign(form, snapshot.value); saveError.value = '' }
async function loadProfile() {
  const id = String(userStore.id), request = ++generation
  loading.value = true; loadError.value = ''
  try {
    const response = await getUserProfile()
    if (!isCurrent(id) || request !== generation) return
    snapshot.value = profileFields(response.data)
    Object.assign(form, snapshot.value)
    accountName.value = response.data?.userName || userStore.name
  } catch (error) { if (isCurrent(id) && request === generation) loadError.value = error?.msg || '个人资料加载失败，请重试' }
  finally { if (isCurrent(id) && request === generation) loading.value = false }
}
async function saveProfile() {
  if (accountSaving.value || loading.value || loadError.value) return
  saveError.value = validateProfile(form)
  if (saveError.value) return
  const id = String(userStore.id), fields = profileFields(form)
  saving.value = true
  try {
    await updateUserProfile(fields)
    if (!isCurrent(id)) return
    snapshot.value = fields; Object.assign(form, fields); userStore.nickName = fields.nickName
    ElMessage.success('个人资料已保存')
  } catch (error) { if (isCurrent(id)) saveError.value = error?.msg || '保存失败，请稍后重试' }
  finally { if (isCurrent(id)) saving.value = false }
}
async function savePassword() {
  if (accountSaving.value || loading.value || loadError.value) return
  passwordError.value = validatePasswordChange(password)
  if (passwordError.value) return
  const id = String(userStore.id)
  passwordSaving.value = true
  try {
    await updateUserPwd(password.oldPassword, password.newPassword)
    if (isCurrent(id)) { resetPassword(); ElMessage.success('密码已修改') }
  } catch (error) { if (isCurrent(id)) passwordError.value = error?.msg || '密码修改失败，请核对原密码后重试' }
  finally { if (isCurrent(id)) passwordSaving.value = false }
}
onMounted(loadProfile)
onBeforeUnmount(() => { active = false; generation += 1; resetPassword() })
</script>

<style scoped>
.ps-profile-page > :deep(.ps-page-header) { min-height: 0; margin: 0; }
.ps-profile-panel {
  --ps-profile-inset: clamp(16px, 2.5cqi, 32px);
  --ps-profile-label-width: clamp(120px, 15cqi, 180px);
  --ps-profile-input-width: 420px;
  overflow: hidden;
  border: 1px solid var(--ps-line);
  border-radius: 12px;
  background: var(--ps-paper);
}
.ps-profile-account { min-width: 0; overflow-wrap: anywhere; }
.ps-profile-account dl { display: flex; flex-wrap: wrap; gap: 0 8px; margin: 0; color: var(--ps-muted); font-size: 13px; }
.ps-profile-account dd { margin: 0; color: var(--ps-ink-2); }
.ps-profile-panel > .ps-profile-form, .ps-profile-security { padding: 20px var(--ps-profile-inset); }
.ps-profile-panel h2 { margin: 0 0 12px; color: var(--ps-ink); font-size: 17px; line-height: 1.4; }
.ps-profile-account h2 { margin-bottom: 4px; font-size: 19px; }
.ps-profile-fields :deep(.el-form-item) {
  display: grid;
  grid-template-columns: var(--ps-profile-label-width) minmax(0, var(--ps-profile-input-width));
  align-items: center;
  margin: 0;
  padding-block: 10px;
  border-bottom: 1px solid var(--ps-line-soft);
}
.ps-profile-form :deep(.el-form-item__label) { color: var(--ps-ink-2); font-size: 14px; }
.ps-profile-form :deep(.el-input__wrapper) { min-height: 40px; border-radius: 6px; }
.ps-profile-gender { gap: 0 16px; }
.ps-profile-gender :deep(.el-radio) { min-height: 44px; margin-right: 0; }
.ps-profile-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 16px 0 0 var(--ps-profile-label-width); }
.ps-profile-actions :deep(.el-button) { margin: 0; }
.ps-profile-save-state { color: #956020; font-size: 12px; }
.ps-profile-error { margin-inline-start: var(--ps-profile-label-width); color: #a43333; font-size: 13px; line-height: 1.6; }
.ps-profile-security { border-top: 1px solid var(--ps-line); }
.ps-profile-security :deep(.el-collapse) { --el-collapse-border-color: var(--ps-line-soft); }
.ps-profile-security :deep(.el-collapse-item__header) { padding-inline: 12px; }
.ps-profile-security :deep(.el-collapse-item__header:hover) { background: var(--el-fill-color-lighter); }
.ps-profile-security :deep(.el-collapse-item__content) { padding-bottom: 16px; }
.ps-profile-password-form { padding-top: 4px; }
@container workspace (max-width: 540px) {
  .ps-profile-panel { --ps-profile-label-width: 0px; }
  .ps-profile-fields :deep(.el-form-item) { grid-template-columns: minmax(0, 1fr); gap: 4px; }
  .ps-profile-form :deep(.el-form-item__label) { height: auto; padding: 0; line-height: 1.5; }
  .ps-profile-form :deep(.el-input__wrapper) { min-height: 44px; }
  .ps-profile-form :deep(.el-input__inner) { font-size: 16px; }
}
</style>
