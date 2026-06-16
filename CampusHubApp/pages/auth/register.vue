<template>
  <view class="register-container">
    <view class="register-header">
      <text class="title">创建账号</text>
      <text class="subtitle">用邮箱注册 CampusHub，开始发布活动和动态</text>
    </view>

    <view class="register-form glass-panel">
      <view class="form-item input-wrap mail-icon">
        <input
          v-model="form.email"
          class="input"
          placeholder="邮箱"
          type="text"
        />
      </view>

      <view class="form-item input-wrap user-icon">
        <input
          v-model="form.nickname"
          class="input"
          placeholder="昵称"
          type="text"
        />
      </view>

      <view class="form-item input-wrap lock-icon">
        <input
          v-model="form.password"
          class="input"
          placeholder="密码（6-20位）"
          password
          type="password"
        />
      </view>

      <view class="form-item input-wrap lock-icon">
        <input
          v-model="form.confirmPassword"
          class="input"
          placeholder="确认密码"
          password
          type="password"
        />
      </view>

      <view class="form-item">
        <view class="verify-code-row">
          <view class="input-wrap shield-icon verify-wrap">
            <input
              v-model="form.verifycode"
              class="input verify-input"
              placeholder="验证码"
              type="number"
            />
          </view>
          <button class="code-btn" :disabled="codeCountdown > 0" @click="sendVerifyCode">
            {{ codeCountdown > 0 ? `${codeCountdown}秒` : '获取验证码' }}
          </button>
        </view>
      </view>

      <button class="register-btn" :loading="loading" @click="handleRegister">注册</button>

      <view class="login-link">
        <text>已有账号？</text>
        <text class="link-text" @click="toLogin">立即登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { authApi } from '@/api/index.js'
import verifyApi from '@/api/verify.js'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'

const form = ref({
  email: '',
  nickname: '',
  password: '',
  confirmPassword: '',
  verifycode: ''
})

const loading = ref(false)
const codeCountdown = ref(0)

const sendVerifyCode = async () => {
  if (!form.value.email) {
    showError('请先输入邮箱')
    return
  }
  
  try {
    await verifyApi.sendRegisterCode(form.value.email)
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

const handleRegister = async () => {
  if (!form.value.email || !form.value.nickname || !form.value.password || !form.value.verifycode) {
    showError('请填写完整信息')
    return
  }
  
  if (form.value.password !== form.value.confirmPassword) {
    showError('两次密码不一致')
    return
  }
  
  if (form.value.password.length < 6 || form.value.password.length > 20) {
    showError('密码长度应为6-20位')
    return
  }
  
  loading.value = true
  showLoading('注册中...')
  
  try {
    await authApi.register({
      email: form.value.email,
      nickname: form.value.nickname,
      password: form.value.password,
      verifycode: parseInt(form.value.verifycode)
    })
    showSuccess('注册成功')
    
    setTimeout(() => {
      uni.navigateBack()
    }, 1000)
  } catch (error) {
    showError(error.message || '注册失败')
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
.register-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 88% 8%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #f8fbff 100%);
  padding: 52rpx 36rpx;
  box-sizing: border-box;
}

.register-header {
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

.register-form {
  padding: 34rpx;
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
  margin-bottom: 20rpx;
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

.user-icon::before {
  width: 18rpx;
  height: 18rpx;
  top: 22rpx;
  left: 31rpx;
  border: 3rpx solid currentColor;
  border-radius: 50%;
}

.user-icon::after {
  width: 34rpx;
  height: 18rpx;
  bottom: 22rpx;
  left: 23rpx;
  border: 3rpx solid currentColor;
  border-bottom: 0;
  border-radius: 18rpx 18rpx 0 0;
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
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.14));
  color: #ffffff;
  border: 1rpx solid rgba(255, 255, 255, 0.58);
  border-radius: 26rpx;
  font-size: 25rpx;
  font-weight: 800;
  color: #1f447a;
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

.register-btn {
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
  margin-bottom: 34rpx;
  padding: 0;
  box-shadow: 0 16rpx 30rpx rgba(31, 68, 122, 0.22);
}

.register-btn:active,
.code-btn:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.login-link {
  text-align: center;
  font-size: 26rpx;
  color: #667085;
}

.link-text {
  color: #1f447a;
  margin-left: 10rpx;
  font-weight: 800;
}
</style>

