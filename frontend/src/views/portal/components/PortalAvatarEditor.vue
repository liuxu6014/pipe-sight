<template>
  <div class="ps-avatar-setting">
    <PortalUserAvatar class="ps-profile-avatar" />
    <slot />
    <el-button :disabled="disabled" @click="open = true">更换头像</el-button>
  </div>
  <el-dialog v-model="open" title="修改头像" width="560px" class="ps-avatar-dialog" append-to-body align-center :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @closed="clearDraft">
    <div v-if="source" class="ps-avatar-crop-layout">
      <div class="ps-avatar-crop">
        <VueCropper ref="cropper" :img="source" :auto-crop="true" :auto-crop-width="200" :auto-crop-height="200" :fixed="true" :fixed-number="[1, 1]" :output-size="1" output-type="png" :can-move="!saving" :can-move-box="!saving" @real-time="preview = $event" @img-load="imageLoaded" />
      </div>
      <div class="ps-avatar-preview" aria-label="头像预览"><div><img v-if="preview.url" :src="preview.url" :style="preview.img" alt="裁剪后的头像预览" /></div><span>头像预览</span></div>
    </div>
    <div :class="{ 'ps-avatar-tools': source }">
      <el-upload
        :class="{ 'ps-avatar-picker': !source }"
        :drag="!source"
        action="#"
        accept="image/jpeg,image/png,image/webp"
        :auto-upload="false"
        :show-file-list="false"
        :disabled="saving"
        :on-change="chooseImage"
      >
        <el-button v-if="source" :disabled="saving">重新选图</el-button>
        <div v-else class="ps-avatar-picker-content">
          <el-icon :size="24" aria-hidden="true"><UploadFilled /></el-icon>
          <strong>点击选择或拖入图片</strong>
          <span>JPG、PNG、WebP，最大 5 MB</span>
        </div>
      </el-upload>
      <template v-if="source">
        <el-button :disabled="saving || !ready" @click="cropper?.changeScale(1)" aria-label="放大头像">放大</el-button>
        <el-button :disabled="saving || !ready" @click="cropper?.changeScale(-1)" aria-label="缩小头像">缩小</el-button>
        <el-button :disabled="saving || !ready" @click="cropper?.rotateRight()">旋转</el-button>
      </template>
    </div>
    <p v-if="error" class="ps-avatar-error" role="alert">{{ error }}</p>
    <template #footer><el-button :disabled="saving" @click="open = false">取消</el-button><el-button v-if="source" type="primary" :loading="saving" :disabled="!ready" @click="saveAvatar">保存头像</el-button></template>
  </el-dialog>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { VueCropper } from 'vue-cropper'
import 'vue-cropper/dist/index.css'
import { uploadAvatar } from '@/api/system/user'
import useUserStore from '@/store/modules/user'
import { avatarUrl, validateAvatarFile } from '@/utils/portal/avatar'
import PortalUserAvatar from './PortalUserAvatar.vue'

const userStore = useUserStore()
defineProps({ disabled: Boolean })
const emit = defineEmits(['saving'])
const open = ref(false), saving = ref(false), source = ref(''), error = ref(''), ready = ref(false)
const cropper = ref(null), preview = ref({})
let reader, sequence = 0, active = true
watch(saving, value => emit('saving', value), { flush: 'sync' })
function clearDraft() {
  sequence += 1; reader?.abort(); source.value = ''; preview.value = {}; error.value = ''; ready.value = false
}
function chooseImage(upload) {
  if (saving.value) return
  error.value = validateAvatarFile(upload.raw)
  if (error.value) return
  reader?.abort()
  const current = ++sequence
  reader = new FileReader()
  reader.onload = () => {
    if (!active || current !== sequence || !open.value) return
    ready.value = false; preview.value = {}; source.value = String(reader.result)
  }
  reader.onerror = () => { if (active && current === sequence) error.value = '图片读取失败，请重新选择' }
  reader.readAsDataURL(upload.raw)
}
function imageLoaded(result) {
  ready.value = result === 'success'
  if (!ready.value) { source.value = ''; error.value = '无法读取该图片，请选择有效图片' }
}
async function saveAvatar() {
  if (saving.value || !source.value || !ready.value || !cropper.value) return
  const id = String(userStore.id)
  saving.value = true; error.value = ''
  try {
    const blob = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('图片处理超时，请重新选择')), 10000)
      try { cropper.value.getCropBlob(value => { clearTimeout(timeout); value?.size ? resolve(value) : reject(new Error('图片处理失败，请重新选择')) }) }
      catch (error) { clearTimeout(timeout); reject(error) }
    })
    if (!active || String(userStore.id) !== id) return
    const data = new FormData()
    data.append('avatarfile', blob, 'avatar.png')
    const response = await uploadAvatar(data)
    if (!active || String(userStore.id) !== id) return
    const url = avatarUrl(response.imgUrl, import.meta.env.VITE_APP_BASE_API)
    if (!url) throw new Error('上传未返回头像地址，请重试')
    userStore.avatar = url
    open.value = false
    ElMessage.success('头像已更新')
  } catch (failure) {
    if (active && String(userStore.id) === id) error.value = failure?.msg || failure?.message || '头像上传失败，请重试'
  } finally { if (active) saving.value = false }
}
onBeforeUnmount(() => { active = false; clearDraft(); emit('saving', false) })
</script>

<style scoped>
.ps-avatar-setting {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 18px var(--ps-profile-inset, 24px);
  border-bottom: 1px solid var(--ps-line-soft);
  background: color-mix(in srgb, var(--ps-blue) 4%, var(--ps-paper));
}
.ps-profile-avatar { flex: none; width: 52px; height: 52px; border-radius: 50%; font-size: 21px; }
:global(.ps-avatar-dialog.el-dialog.is-align-center) { margin-top: auto !important; }
.ps-avatar-crop-layout { display: grid; grid-template-columns: minmax(0, 1fr) 120px; gap: 20px; align-items: center; }
.ps-avatar-crop { height: 300px; min-width: 0; }
.ps-avatar-preview { text-align: center; font-size: 12px; color: var(--ps-muted); }
.ps-avatar-preview > div { width: 100px; height: 100px; border-radius: 50%; overflow: hidden; margin: 0 auto 12px; background: #eef3f6; }
.ps-avatar-preview img { max-width: none; }
.ps-avatar-picker :deep(.el-upload) { display: block; }
.ps-avatar-picker :deep(.el-upload-dragger) {
  display: grid;
  place-items: center;
  min-height: 168px;
  padding: 20px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
.ps-avatar-picker :deep(.el-upload-dragger:hover),
.ps-avatar-picker :deep(.el-upload-dragger.is-dragover),
.ps-avatar-picker :deep(.el-upload:focus-visible .el-upload-dragger) {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.ps-avatar-picker-content { display: grid; justify-items: center; gap: 8px; line-height: 1.5; }
.ps-avatar-picker-content .el-icon { color: var(--el-color-primary); }
.ps-avatar-picker-content strong { color: var(--el-text-color-primary); font-size: 15px; }
.ps-avatar-picker-content span { color: var(--el-text-color-regular); font-size: 12px; }
.ps-avatar-tools { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.ps-avatar-tools :deep(.el-button) { margin: 0; }
.ps-avatar-error { color: #a43333; line-height: 1.6; }
@media (max-width: 600px) { .ps-avatar-crop-layout { grid-template-columns: minmax(0, 1fr); } .ps-avatar-preview { display: none; } .ps-avatar-crop { height: 280px; } }
</style>
