<template>
  <view class="forgot-password-container">
    <view class="auth-header">
      <text class="title">重置密码</text>
      <text class="subtitle">通过注册邮箱完成验证后设置新密码</text>
    </view>

    <view class="form glass-panel">
      <view class="step-indicator">
        <view
          v-for="step in 3"
          :key="step"
          class="step-dot"
          :class="{ active: currentStep === step, done: currentStep > step }"
        >
          <text>{{ step }}</text>
        </view>
        <view class="step-line"></view>
      </view>
      <text class="step-text">{{ stepTitle }}</text>

      <view v-if="currentStep === 1" class="step-content">
        <view class="form-item">
          <text class="label">邮箱</text>
          <view class="input-wrap mail-icon">
            <input
              v-model="form.email"
              class="input"
              placeholder="请输入注册邮箱"
              type="text"
            />
          </view>
        </view>
        <button class="submit-btn" :loading="loading" @click="handleVerifyEmail">下一步</button>
      </view>

      <view v-if="currentStep === 2" class="step-content">
        <view class="form-item">
          <text class="label">验证码</text>
          <view class="verify-code-row">
            <view class="input-wrap shield-icon verify-wrap">
              <input
                v-model="form.verifyCode"
                class="input verify-input"
                placeholder="请输入验证码"
                type="number"
              />
            </view>
            <button class="code-btn" :disabled="codeCountdown > 0" @click="sendCode">
              {{ codeCountdown > 0 ? `${codeCountdown}秒` : '重新发送' }}
            </button>
          </view>
        </view>
        <button class="submit-btn" :loading="loading" @click="handleVerifyCode">下一步</button>
      </view>

      <view v-if="currentStep === 3" class="step-content">
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
        <button class="submit-btn" :loading="loading" @click="handleResetPassword">完成</button>
      </view>
      
      <view class="back-link">
        <text class="link-text" @click="toLogin">返回登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { authApi } from '@/api/index.js'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'

const currentStep = ref(1)
const loading = ref(false)
const codeCountdown = ref(0)

const form = ref({
  email: '',
  verifyCode: '',
  newPassword: '',
  confirmPassword: ''
})

const stepTitle = computed(() => {
  if (currentStep.value === 1) return '验证注册邮箱'
  if (currentStep.value === 2) return '输入邮箱验证码'
  return '设置新的登录密码'
})

const handleVerifyEmail = async () => {
  if (!form.value.email) {
    showError('请输入邮箱')
    return
  }
  
  loading.value = true
  showLoading('验证中...')
  
  try {
    await authApi.verifyEmailForReset(form.value.email)
    showSuccess('邮箱验证通过')
    currentStep.value = 2
    sendCode()
  } catch (error) {
    showError(error.message || '验证失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const sendCode = async () => {
  try {
    await authApi.sendResetCode(form.value.email)
    showSuccess('验证码已发送')
    codeCountdown.value = 60
    const timer = setInterval(() => {
      codeCountdown.value--
      if (codeCountdown.value <= 0) {
        clearInterval(timer)
      }
    }, 1000)
  } catch (error) {
    showError(error.message || '发送失败')
  }
}

const handleVerifyCode = async () => {
  if (!form.value.verifyCode) {
    showError('请输入验证码')
    return
  }
  
  loading.value = true
  showLoading('验证中...')
  
  try {
    await authApi.verifyResetCode(form.value.email, parseInt(form.value.verifyCode))
    showSuccess('验证码正确')
    currentStep.value = 3
  } catch (error) {
    showError(error.message || '验证失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const handleResetPassword = async () => {
  if (!form.value.newPassword || !form.value.confirmPassword) {
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
  showLoading('重置中...')
  
  try {
    await authApi.resetPassword(
      form.value.email,
      parseInt(form.value.verifyCode),
      form.value.newPassword
    )
    showSuccess('密码重置成功')
    
    setTimeout(() => {
      uni.navigateBack()
    }, 1000)
  } catch (error) {
    showError(error.message || '重置失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const toLogin = () => {
  uni.navigateBack()
}
</script>

<style scoped>
.forgot-password-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 88% 8%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #f8fbff 100%);
  padding: 52rpx 36rpx;
  box-sizing: border-box;
}

.auth-header {
  margin-bottom: 28rpx;
  padding: 24rpx 6rpx 8rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.title {
  font-size: 52rpx;
  line-height: 1.1;
  font-weight: 900;
  color: #172033;
}

.subtitle {
  font-size: 25rpx;
  color: #667085;
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

.step-indicator {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4rpx 20rpx 24rpx;
}

.step-line {
  position: absolute;
  left: 30rpx;
  right: 30rpx;
  top: 28rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: rgba(203, 216, 231, 0.72);
  z-index: -1;
}

.step-dot {
  width: 58rpx;
  height: 58rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(255, 255, 255, 0.70);
  background: rgba(255, 255, 255, 0.62);
  color: #8a94a6;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.82),
    0 8rpx 18rpx rgba(22, 47, 84, 0.08);
}

.step-dot text {
  font-size: 24rpx;
  font-weight: 850;
}

.step-dot.active,
.step-dot.done {
  color: #ffffff;
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
}

.step-text {
  position: relative;
  z-index: 1;
  display: block;
  margin-bottom: 30rpx;
  font-size: 28rpx;
  color: #172033;
  font-weight: 900;
  text-align: center;
}

.step-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
}

.form-item {
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

.mail-icon::before {
  width: 32rpx;
  height: 24rpx;
  border: 3rpx solid currentColor;
  border-radius: 8rpx;
}

.mail-icon::after {
  width: 22rpx;
  height: 22rpx;
  top: 29rpx;
  left: 29rpx;
  border-left: 3rpx solid currentColor;
  border-bottom: 3rpx solid currentColor;
  transform: rotate(-45deg);
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

.shield-icon::before {
  width: 32rpx;
  height: 36rpx;
  top: 25rpx;
  border: 3rpx solid currentColor;
  border-radius: 16rpx 16rpx 18rpx 18rpx;
}

.shield-icon::after {
  width: 14rpx;
  height: 7rpx;
  top: 38rpx;
  left: 33rpx;
  border-left: 3rpx solid currentColor;
  border-bottom: 3rpx solid currentColor;
  transform: rotate(-45deg);
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

.verify-code-row {
  display: flex;
  gap: 16rpx;
  align-items: center;
}

.verify-wrap {
  flex: 1;
  min-width: 0;
}

.verify-input {
  padding-right: 16rpx;
}

.code-btn {
  width: 204rpx;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 26rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.58);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.14));
  color: #1f447a;
  font-size: 25rpx;
  font-weight: 800;
  padding: 0;
  box-shadow:
    0 12rpx 24rpx rgba(22, 47, 84, 0.10),
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18rpx) saturate(1.55);
  backdrop-filter: blur(18rpx) saturate(1.55);
}

.code-btn[disabled] {
  color: #8a94a6;
  background: rgba(238, 244, 250, 0.66);
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
  margin-top: 20rpx;
  padding: 0;
  box-shadow: 0 16rpx 30rpx rgba(31, 68, 122, 0.22);
}

.submit-btn:active,
.code-btn:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.back-link {
  text-align: center;
  margin-top: 40rpx;
}

.link-text {
  color: #1f447a;
  font-size: 26rpx;
  font-weight: 800;
}
</style>

