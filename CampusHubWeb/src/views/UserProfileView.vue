<template>
  <div class="user-profile-view">
    <!-- 顶部个人信息卡片 -->
    <el-card class="profile-header-card" shadow="hover">
      <div class="profile-header">
        <div class="avatar-area">
          <el-avatar
            :size="88"
            :src="profileAvatarUrl"
            class="avatar"
          >
            {{ currentUserInitial }}
          </el-avatar>
        </div>

        <div class="base-info">
          <div class="name-row">
            <h2 class="nickname">{{ currentUser?.nickname || '未命名用户' }}</h2>
            <el-tag size="small" type="info" v-if="currentUser">
              {{ userTypeLabel }}
            </el-tag>
          </div>
          <p class="email" v-if="currentUser?.email">{{ currentUser.email }}</p>
          <p class="signature" v-if="currentUser?.signature">
            {{ currentUser.signature }}
          </p>
          <div class="meta-row" v-if="currentUser">
            <span>用户ID：{{ currentUser.id }}</span>
            <span>注册时间：{{ formatProfileTime(currentUser.createdAt) }}</span>
          </div>
        </div>

        <div class="profile-actions">
          <div class="avatar-actions">
            <el-button size="small" @click="triggerAvatarSelect" :loading="avatarUploading">
              更换头像
            </el-button>
            <input
              ref="avatarInputRef"
              type="file"
              accept="image/*"
              class="hidden-file-input"
              @change="handleAvatarChange"
            />
            <p class="avatar-tip">支持 JPG/PNG，大小不超过 2MB</p>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 主要功能区域：标签页 -->
    <el-card class="profile-main-card" shadow="never">
      <el-tabs v-model="activeTab" type="border-card" class="profile-tabs">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <div class="pane-heading">
            <h3>基本信息</h3>
            <p>同步更新昵称、头像与对外展示签名。</p>
          </div>
          <el-form
            :model="editableUser"
            label-position="top"
            class="profile-form"
          >
            <el-form-item label="昵称">
              <el-input
                v-model="editableUser.nickname"
                maxlength="50"
                show-word-limit
                placeholder="请输入昵称"
              />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="editableUser.email" disabled />
            </el-form-item>
            <el-form-item label="个性签名">
              <el-input
                v-model="editableUser.signature"
                type="textarea"
                :rows="3"
                maxlength="255"
                show-word-limit
                placeholder="写点什么，让大家更了解你吧"
              />
            </el-form-item>
            <el-form-item label="账号类型" v-if="currentUser">
              <el-tag type="info">{{ userTypeLabel }}</el-tag>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSaveProfile" :loading="savingProfile">
                保存修改
              </el-button>
              <el-button @click="resetProfile" :disabled="savingProfile">
                重置
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 账户安全 -->
        <el-tab-pane label="账户安全" name="security">
          <div class="pane-heading">
            <h3>账户安全</h3>
            <p>修改后请使用新密码重新确认后续登录。</p>
          </div>
          <el-form :model="passwordForm" label-position="top" class="security-form">
            <el-form-item label="当前密码">
              <el-input
                v-model="passwordForm.oldPassword"
                type="password"
                show-password
                autocomplete="current-password"
                placeholder="请输入当前密码"
              />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                show-password
                autocomplete="new-password"
                placeholder="6-20 位新密码"
              />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                show-password
                autocomplete="new-password"
                placeholder="请再次输入新密码"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleChangePassword" :loading="changingPassword">
                修改密码
              </el-button>
              <span class="security-tip">密码长度需在 6-20 位之间，建议包含字母与数字。</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 仅保留核心：基本信息与账户安全 -->
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import { useAuthStore } from '../stores/auth'

const userStore = useUserStore()
const authStore = useAuthStore()

const activeTab = ref('basic')
const avatarInputRef = ref(null)
const avatarUploading = ref(false)
const savingProfile = ref(false)
const changingPassword = ref(false)

const currentUser = computed(() => userStore.currentUser)

const fileBaseUrl =
  import.meta.env.VITE_FILE_BASE_URL || (import.meta.env.PROD ? import.meta.env.BASE_URL.replace(/\/$/, '') : 'http://localhost:8080')

const resolveMediaUrl = (url) => {
  if (!url) return ''
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

const profileAvatarUrl = computed(() => {
  return currentUser.value?.avatarUrl ? resolveMediaUrl(currentUser.value.avatarUrl) : ''
})

const currentUserInitial = computed(() => {
  if (currentUser.value?.nickname) {
    return currentUser.value.nickname.slice(0, 1)
  }
  if (currentUser.value?.email) {
    return currentUser.value.email.slice(0, 1).toUpperCase()
  }
  return '用'
})

const userTypeLabel = computed(() => {
  if (!currentUser.value) return '普通用户'
  const userType = currentUser.value.userType
  if (userType === 1 || userType === 'ADMIN') return '管理员'
  return '普通用户'
})

const formatProfileTime = (value) => {
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const editableUser = reactive({
  nickname: '',
  email: '',
  signature: ''
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 已移除：隐私设置、通知设置、收藏/历史、帮助反馈等未实现后端依赖功能

const fillEditableFromUser = () => {
  if (!currentUser.value) return
  editableUser.nickname = currentUser.value.nickname || ''
  editableUser.email = currentUser.value.email || ''
  editableUser.signature = currentUser.value.signature || ''
}

const initUser = async () => {
  try {
    if (!currentUser.value) {
      await userStore.fetchCurrentUser()
    }
    fillEditableFromUser()
  } catch (error) {
    console.error('加载用户信息失败', error)
    ElMessage.error(error?.message || '加载用户信息失败')
  }
}

const triggerAvatarSelect = () => {
  if (avatarInputRef.value) {
    avatarInputRef.value.click()
  }
}

const handleAvatarChange = async (event) => {
  const file = event.target.files && event.target.files[0]
  if (!file) return

  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('仅支持图片文件作为头像')
    event.target.value = ''
    return
  }

  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB')
    event.target.value = ''
    return
  }

  try {
    avatarUploading.value = true
    await userStore.uploadAvatar(file)

    if (userStore.currentUser) {
      authStore.setUser({
        ...(authStore.user || {}),
        ...userStore.currentUser
      })
    }

    ElMessage.success('头像更新成功')
  } catch (error) {
    console.error('头像上传失败', error)
    ElMessage.error(error?.message || '头像上传失败')
  } finally {
    avatarUploading.value = false
    event.target.value = ''
  }
}

const handleSaveProfile = async () => {
  if (!editableUser.nickname.trim()) {
    ElMessage.error('昵称不能为空')
    return
  }

  try {
    savingProfile.value = true
    const payload = {
      nickname: editableUser.nickname.trim(),
      signature: editableUser.signature?.trim() || '',
      avatarUrl: currentUser.value?.avatarUrl || ''
    }
    await userStore.updateUser(payload)

    if (userStore.currentUser) {
      authStore.setUser({
        ...(authStore.user || {}),
        ...userStore.currentUser
      })
    }

    ElMessage.success('个人信息已更新')
  } catch (error) {
    console.error('更新个人信息失败', error)
    ElMessage.error(error?.message || '更新个人信息失败')
  } finally {
    savingProfile.value = false
  }
}

const resetProfile = () => {
  fillEditableFromUser()
  ElMessage.info('已恢复为当前保存的信息')
}

const handleChangePassword = async () => {
  if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
    ElMessage.error('请完整填写所有密码字段')
    return
  }

  if (passwordForm.newPassword.length < 6 || passwordForm.newPassword.length > 20) {
    ElMessage.error('新密码长度需在 6-20 位之间')
    return
  }

  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  try {
    changingPassword.value = true
    await userStore.updatePassword({
      oldPassword: passwordForm.oldPassword,
      newPassword: passwordForm.newPassword
    })
    ElMessage.success('密码修改成功')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (error) {
    console.error('修改密码失败', error)
    const message = error?.message || error?.msg || '修改密码失败'
    ElMessage.error(message)
  } finally {
    changingPassword.value = false
  }
}

onMounted(async () => {
  await initUser()
})
</script>

<style scoped lang="scss">
.user-profile-view {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.profile-header-card {
  overflow: hidden;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 24px;
  min-height: 164px;
  padding: 6px 0;
}

.avatar-area {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 118px;
  flex: 0 0 118px;
}

.avatar {
  border: 2px solid color-mix(in srgb, var(--ch-primary) 14%, var(--ch-border));
  color: #fff;
  background: linear-gradient(135deg, #1f66ff, #16a873);
  font-size: 28px;
  font-weight: 900;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.avatar-tip {
  margin: 0;
  font-size: 12px;
  color: var(--ch-muted);
  text-align: right;
}

.hidden-file-input {
  display: none;
}

.base-info {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.nickname {
  margin: 0;
  color: var(--ch-text);
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.1;
  font-weight: 900;
}

.email {
  margin: 0;
  color: var(--ch-text);
  font-size: 15px;
}

.signature {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--ch-muted);
}

.meta-row {
  margin-top: 16px;
  font-size: 13px;
  color: var(--ch-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.meta-row span {
  border: 1px solid var(--ch-border);
  border-radius: 999px;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--ch-bg-soft) 76%, transparent);
}

.profile-actions {
  flex: 0 0 auto;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 180px;
}

.profile-main-card {
  margin-top: 4px;
}

.profile-tabs {
  border-radius: var(--ch-radius) !important;
  overflow: hidden;
}

.profile-tabs :deep(.el-tabs__header) {
  background: var(--ch-bg-soft);
}

.profile-tabs :deep(.el-tabs__item.is-active),
.profile-tabs :deep(.el-tabs__content),
.profile-tabs :deep(.el-tab-pane) {
  background: var(--ch-surface-solid);
  color: var(--ch-text);
}

.profile-form,
.security-form,
.feedback-form {
  max-width: 640px;
}

.pane-heading {
  margin-bottom: 18px;
}

.pane-heading h3 {
  margin: 0;
  color: var(--ch-text);
  font-size: 18px;
  line-height: 1.2;
}

.pane-heading p {
  margin: 6px 0 0;
  color: var(--ch-muted);
  font-size: 13px;
}

.section-description {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--ch-muted);
}

.security-tip {
  font-size: 12px;
  color: var(--ch-muted);
  margin-left: 12px;
}

.settings-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 8px;
  background-color: #f5f7fa;
}

.settings-text {
  max-width: 80%;
}

.settings-text h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.settings-text p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
}

.settings-actions {
  margin-top: 8px;
}

.collections-row,
.help-row {
  margin-top: 4px;
}

.sub-card {
  height: 100%;
}

.sub-card-header {
  margin-bottom: 8px;
}

.sub-card-header h3 {
  margin: 0;
  font-size: 16px;
}

.sub-card-desc {
  font-size: 12px;
  color: #909399;
}

.empty-wrap {
  padding: 12px 0;
}

.faq-list {
  list-style: none;
  padding: 0;
  margin: 8px 0;
  font-size: 13px;
  color: #606266;
}

.faq-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

@media (max-width: 768px) {
  .profile-header {
    display: grid;
    grid-template-columns: 72px minmax(0, 1fr);
    gap: 16px;
    min-height: 0;
  }

  .avatar-area {
    width: 72px;
    flex-basis: 72px;
  }

  .avatar {
    width: 72px !important;
    height: 72px !important;
    font-size: 24px;
  }

  .profile-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
    min-width: 0;
  }

  .avatar-actions {
    align-items: flex-start;
  }

  .avatar-tip {
    text-align: left;
  }

  .nickname {
    font-size: 28px;
  }

  .meta-row {
    gap: 8px;
  }

  .profile-main-card :deep(.el-tabs__item) {
    height: 46px;
    padding: 0 18px;
    font-size: 15px;
  }

  .profile-main-card :deep(.el-tabs__content) {
    padding: 18px !important;
  }

  .profile-form,
  .security-form {
    max-width: none;
  }

  .settings-item {
    align-items: flex-start;
  }

  .settings-text {
    max-width: 70%;
  }
}
</style>
