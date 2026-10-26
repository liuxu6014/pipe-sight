<template>
  <div class="ps-page ps-profile-page">
    <el-skeleton v-if="loading" :rows="6" animated />
    <div v-else-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}</span><el-button @click="loadProfile">重新加载</el-button></div>
    <section v-else class="ps-profile-panel" aria-label="个人账户设置">
      <el-tabs v-model="activeTab" class="ps-profile-tabs">
        <el-tab-pane label="个人资料" name="basic" :disabled="passwordSaving" />
        <el-tab-pane label="账户安全" name="security" :disabled="saving || avatarSaving" />
      </el-tabs>
      <el-form v-if="activeTab === 'basic'" class="ps-profile-form" label-position="top" :disabled="saving" @submit.prevent="saveProfile">
        <PortalAvatarEditor @saving="avatarSaving = $event" />
        <div class="ps-profile-fields">
          <el-form-item label="登录账号"><el-input :model-value="accountName" readonly aria-label="登录账号，只读" :prefix-icon="User" /><small class="ps-profile-field-hint">登录账号不可修改</small></el-form-item>
          <el-form-item label="昵称" required><el-input v-model="form.nickName" aria-label="昵称" maxlength="30" autocomplete="nickname" show-word-limit /></el-form-item>
          <el-form-item label="手机号码"><el-input v-model="form.phonenumber" aria-label="手机号码" maxlength="11" inputmode="tel" autocomplete="tel" :prefix-icon="Phone" placeholder="填写手机号码" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="form.email" aria-label="邮箱" maxlength="50" autocomplete="email" :prefix-icon="Message" placeholder="填写常用邮箱" /></el-form-item>
        </div>
        <el-form-item label="性别"><el-radio-group v-model="form.sex" aria-label="性别"><el-radio value="0">男</el-radio><el-radio value="1">女</el-radio><el-radio value="2">不设置</el-radio></el-radio-group></el-form-item>
        <p v-if="saveError" class="ps-profile-error" role="alert">{{ saveError }}</p>
        <div class="ps-profile-actions">
          <span v-if="isDirty" class="ps-profile-save-state" role="status">有未保存的修改</span>
          <div><el-button :disabled="saving || avatarSaving || !isDirty" @click="resetProfile">撤销修改</el-button><el-button type="primary" native-type="submit" :disabled="avatarSaving || !isDirty" :loading="saving">保存资料</el-button></div>
        </div>
      </el-form>
      <el-form v-else class="ps-profile-form ps-profile-security-form" label-position="top" :disabled="passwordSaving" @submit.prevent="savePassword">
        <el-form-item label="原密码" required><el-input v-model="password.oldPassword" aria-label="原密码" type="password" autocomplete="current-password" placeholder="请输入当前登录密码" show-password /></el-form-item>
        <el-form-item label="新密码" required><el-input v-model="password.newPassword" aria-label="新密码" type="password" autocomplete="new-password" maxlength="20" placeholder="设置 6–20 个字符的新密码" show-password /></el-form-item>
        <el-form-item label="确认新密码" required><el-input v-model="password.confirmPassword" aria-label="确认新密码" type="password" autocomplete="new-password" maxlength="20" placeholder="再次输入新密码" show-password /></el-form-item>
        <p v-if="passwordError" class="ps-profile-error" role="alert">{{ passwordError }}</p>
        <div class="ps-profile-actions"><div><el-button :disabled="passwordSaving" @click="resetPassword">清空输入</el-button><el-button type="primary" native-type="submit" :loading="passwordSaving">修改密码</el-button></div></div>
      </el-form>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Phone, Message } from '@element-plus/icons-vue'
import PortalAvatarEditor from '../components/PortalAvatarEditor.vue'
import useUserStore from '@/store/modules/user'
import { getUserProfile, updateUserProfile, updateUserPwd } from '@/api/system/user'
import { profileFields, validateProfile, validatePasswordChange } from '@/utils/portal/profile'

const userStore = useUserStore()
const activeTab = ref('basic')
const avatarSaving = ref(false)
const loading = ref(true), loadError = ref(''), saveError = ref(''), passwordError = ref('')
const saving = ref(false), passwordSaving = ref(false), accountName = ref('')
const form = reactive(profileFields())
const password = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const snapshot = ref(profileFields())
const isDirty = computed(() => JSON.stringify(profileFields(form)) !== JSON.stringify(snapshot.value))
let active = true, generation = 0
const isCurrent = id => active && String(userStore.id) === id
function resetPassword() { Object.assign(password, { oldPassword: '', newPassword: '', confirmPassword: '' }) }
function resetProfile() { Object.assign(form, snapshot.value); saveError.value = '' }
watch(activeTab, () => { resetPassword(); passwordError.value = '' })
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
  if (saving.value || avatarSaving.value || loading.value || loadError.value) return
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
  if (passwordSaving.value) return
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
.ps-profile-page { max-width: 900px; margin-inline: auto; }
.ps-profile-panel { padding: 0 24px 20px; border: 1px solid var(--ps-line); border-radius: 12px; background: #fff; min-width: 0; }
.ps-profile-tabs :deep(.el-tabs__header) { margin-bottom: 18px; }
.ps-profile-tabs :deep(.el-tabs__item) { height: 48px; font-size: 15px; }
.ps-profile-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--ps-line); }
.ps-profile-tabs :deep(.el-tabs__content) { display: none; }
.ps-profile-form :deep(.ps-avatar-setting) { gap: 16px; padding-bottom: 16px; margin-bottom: 16px; }
.ps-profile-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 20px; }
.ps-profile-form :deep(.el-form-item) { margin-bottom: 14px; }
.ps-profile-form :deep(.el-form-item__label) { margin-bottom: 6px; color: var(--ps-ink-2); font-size: 14px; }
.ps-profile-form :deep(.el-input__wrapper) { min-height: 44px; border-radius: 6px; }
.ps-profile-form :deep(.el-input__inner[readonly]) { color: var(--ps-muted); }
.ps-profile-form :deep(.el-radio) { min-height: 44px; }
.ps-profile-field-hint { margin-top: 4px; color: var(--ps-muted); font-size: 12px; }
.ps-profile-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 4px; padding-top: 12px; border-top: 1px solid var(--ps-line-soft); }
.ps-profile-actions > div { display: flex; gap: 10px; margin-left: auto; }
.ps-profile-actions :deep(.el-button) { margin-left: 0; min-height: 44px; min-width: 96px; }
.ps-profile-save-state { color: #956020; font-size: 12px; }
.ps-profile-error { color: #a43333; font-size: 13px; line-height: 1.6; }
.ps-profile-security-form { max-width: 520px; }
@media (max-width: 600px) {
  .ps-profile-panel { padding: 0 16px 16px; }
  .ps-profile-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
  .ps-profile-fields { grid-template-columns: minmax(0, 1fr); }
  .ps-profile-form :deep(.el-input__inner) { font-size: 16px; }
}
</style>
