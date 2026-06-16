<template>
  <view class="change-password-container">
    <view class="page-header">
      <text class="page-title">修改密码</text>
      <text class="page-subtitle">建议使用 6-20 位密码，并避免与其他平台重复。</text>
    </view>

    <view class="form glass-panel">
      <view class="form-item">
        <text class="label">旧密码</text>
        <view class="input-wrap lock-icon">
          <input
            v-model="form.oldPassword"
            class="input"
            placeholder="请输入旧密码"
            password
            type="password"
          />
        </view>
      </view>

      <view class="form-item">
        <text class="label">新密码</text>
        <view class="input-wrap lock-icon">
          <input
            v-model="form.newPassword"
            class="input"
            placeholder="请输入新密码（6-20位）"
            password
            type="password"
          />
        </view>
      </view>

      <view class="form-item">
        <text class="label">确认新密码</text>
        <view class="input-wrap lock-icon">
          <input
            v-model="form.confirmPassword"
            class="input"
            placeholder="请再次输入新密码"
            password
            type="password"
          />
        </view>
      </view>

      <button class="submit-btn" :loading="loading" @click="handleSubmit">修改密码</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from 'vuex'
import { userApi } from '@/api/index.js'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'

const store = useStore()

const form = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const loading = ref(false)

const handleSubmit = async () => {
  if (!form.value.oldPassword || !form.value.newPassword || !form.value.confirmPassword) {
    showError('请填写完整信息')
    return
  }
  
  if (form.value.newPassword !== form.value.confirmPassword) {
    showError('两次密码不一致')
    return
  }
  
  if (form.value.newPassword.length < 6 || form.value.newPassword.length > 20) {
    showError('密码长度应为6-20位')
    return
  }
  
  loading.value = true
  showLoading('修改中...')
  
  try {
    const userId = store.getters['user/userId']
    await userApi.changePassword(userId, {
      oldPassword: form.value.oldPassword,
      newPassword: form.value.newPassword
    })
    showSuccess('修改成功')
    
    setTimeout(() => {
      uni.navigateBack()
    }, 1000)
  } catch (error) {
    showError(error.message || '修改失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}
</script>

<style scoped>
.change-password-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 88% 8%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #f8fbff 100%);
  padding: 48rpx 34rpx;
  box-sizing: border-box;
}

.page-header {
  padding: 24rpx 6rpx 28rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.page-title {
  color: #172033;
  font-size: 52rpx;
  font-weight: 900;
  line-height: 1.1;
}

.page-subtitle {
  color: #667085;
  font-size: 25rpx;
  line-height: 1.5;
}

.form {
  padding: 36rpx 34rpx 34rpx;
}

.glass-panel {
  position: relative;
  overflow: hidden;
  border-radius: 36rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.70);
  background:
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.74), transparent 34%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.86), rgba(244, 250, 255, 0.62));
  box-shadow:
    0 22rpx 48rpx rgba(22, 47, 84, 0.13),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.92),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.46);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.45);
  backdrop-filter: blur(24rpx) saturate(1.45);
}

.glass-panel::before {
  content: "";
  position: absolute;
  left: 24rpx;
  right: 24rpx;
  top: 10rpx;
  height: 28rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.68), rgba(255, 255, 255, 0.06));
  pointer-events: none;
}

.form-item {
  position: relative;
  z-index: 1;
  margin-bottom: 30rpx;
}

.label {
  display: block;
  font-size: 28rpx;
  font-weight: 800;
  color: #263244;
  margin-bottom: 16rpx;
}

.input-wrap {
  position: relative;
  min-height: 88rpx;
  border-radius: 26rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  background: rgba(255, 255, 255, 0.64);
  box-shadow:
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.82),
    inset -1rpx -1rpx 1rpx rgba(255, 255, 255, 0.42);
  display: flex;
  align-items: center;
}

.input-wrap::before,
.input-wrap::after {
  content: "";
  position: absolute;
  left: 24rpx;
  box-sizing: border-box;
  color: #1f447a;
  pointer-events: none;
}

.lock-icon::before {
  width: 32rpx;
  height: 25rpx;
  bottom: 22rpx;
  border: 3rpx solid currentColor;
  border-radius: 8rpx;
}

.lock-icon::after {
  width: 22rpx;
  height: 21rpx;
  top: 20rpx;
  left: 29rpx;
  border: 3rpx solid currentColor;
  border-bottom: 0;
  border-radius: 16rpx 16rpx 0 0;
}

.input {
  width: 100%;
  height: 86rpx;
  padding: 0 24rpx 0 76rpx;
  border: none;
  background: transparent;
  font-size: 28rpx;
  color: #172033;
  box-sizing: border-box;
}

.submit-btn {
  width: 100%;
  height: 90rpx;
  line-height: 90rpx;
  background:
    linear-gradient(135deg, rgba(47, 126, 216, 0.96), rgba(31, 68, 122, 0.96));
  color: #ffffff;
  border-radius: 28rpx;
  font-size: 32rpx;
  font-weight: 850;
  border: none;
  margin-top: 16rpx;
  padding: 0;
  box-shadow: 0 16rpx 30rpx rgba(31, 68, 122, 0.22);
}

.submit-btn:active {
  transform: scale(0.98);
  opacity: 0.9;
}
</style>

