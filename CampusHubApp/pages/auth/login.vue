<template>
  <view class="login-container">
    <view class="auth-hero">
      <view class="brand-mark">
        <view class="brand-ring"></view>
        <text>CH</text>
      </view>
      <view class="hero-copy">
        <text class="app-title">CampusHub</text>
        <text class="app-subtitle">登录后继续管理你的校园活动与动态</text>
      </view>
    </view>

    <view class="login-form glass-panel">
      <view class="form-title-block">
        <text class="form-title">欢迎回来</text>
        <text class="form-desc">使用邮箱和密码进入 CampusHub</text>
      </view>

      <view class="form-item input-wrap mail-icon">
        <input
          v-model="form.identifier"
          class="input"
          placeholder="邮箱"
          type="text"
        />
      </view>

      <view class="form-item input-wrap lock-icon">
        <input
          v-model="form.password"
          class="input"
          placeholder="密码"
          password
          type="password"
        />
      </view>

      <view class="form-actions">
        <text class="link-text" @click="toForgotPassword">忘记密码？</text>
      </view>

      <button class="login-btn" :loading="loading" @click="handleLogin">登录</button>

      <view class="register-link">
        <text>还没有账号？</text>
        <text class="link-text" @click="toRegister">立即注册</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from 'vuex'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'

const store = useStore()

const form = ref({
  identifier: '',
  password: ''
})

const loading = ref(false)

const handleLogin = async () => {
  if (!form.value.identifier || !form.value.password) {
    showError('请填写完整信息')
    return
  }
  
  loading.value = true
  showLoading('登录中...')
  
  try {
    // 确保传递的是普通对象，而不是响应式对象
    const loginData = {
      identifier: form.value.identifier.trim(),
      password: form.value.password
    }
    
    // 直接调用 store 的 login action，它会处理登录和状态保存
    await store.dispatch('user/login', loginData)
    showSuccess('登录成功')
    
    // 跳转到首页
    setTimeout(() => {
      uni.switchTab({
        url: '/pages/index/index'
      })
    }, 500)
  } catch (error) {
    showError(error.message || '登录失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const toRegister = () => {
  uni.navigateTo({
    url: '/pages/auth/register'
  })
}

const toForgotPassword = () => {
  uni.navigateTo({
    url: '/pages/auth/forgot-password'
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 88% 8%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #f8fbff 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 56rpx 36rpx;
  box-sizing: border-box;
}

.auth-hero {
  margin-bottom: 34rpx;
  padding: 34rpx 10rpx 18rpx;
  display: flex;
  align-items: center;
  gap: 22rpx;
}

.brand-mark {
  position: relative;
  width: 96rpx;
  height: 96rpx;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.68);
  background:
    radial-gradient(circle at 26% 12%, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.18) 34%, transparent 58%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.14));
  box-shadow:
    0 20rpx 44rpx rgba(22, 47, 84, 0.16),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.88),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.46);
  -webkit-backdrop-filter: blur(22rpx) saturate(1.75);
  backdrop-filter: blur(22rpx) saturate(1.75);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex: 0 0 96rpx;
}

.brand-mark text {
  position: relative;
  z-index: 1;
  color: #173b68;
  font-size: 30rpx;
  font-weight: 900;
}

.brand-ring {
  position: absolute;
  inset: 22rpx;
  border: 4rpx solid rgba(23, 59, 104, 0.76);
  border-radius: 50%;
}

.brand-ring::after {
  content: "";
  position: absolute;
  right: -8rpx;
  bottom: 2rpx;
  width: 16rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: rgba(23, 59, 104, 0.76);
  transform: rotate(45deg);
}

.hero-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.app-title {
  display: block;
  font-size: 54rpx;
  line-height: 1.08;
  font-weight: 900;
  color: #172033;
}

.app-subtitle {
  display: block;
  font-size: 25rpx;
  color: #667085;
  line-height: 1.45;
}

.login-form {
  padding: 38rpx 34rpx 34rpx;
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

.form-title-block {
  position: relative;
  z-index: 1;
  margin-bottom: 30rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.form-title {
  color: #172033;
  font-size: 38rpx;
  font-weight: 900;
}

.form-desc {
  color: #8a94a6;
  font-size: 24rpx;
}

.form-item {
  margin-bottom: 22rpx;
}

.input-wrap {
  position: relative;
  min-height: 92rpx;
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
  top: 31rpx;
  left: 29rpx;
  border-left: 3rpx solid currentColor;
  border-bottom: 3rpx solid currentColor;
  transform: rotate(-45deg);
}

.lock-icon::before {
  width: 32rpx;
  height: 25rpx;
  bottom: 24rpx;
  border: 3rpx solid currentColor;
  border-radius: 8rpx;
}

.lock-icon::after {
  width: 22rpx;
  height: 21rpx;
  top: 22rpx;
  left: 29rpx;
  border: 3rpx solid currentColor;
  border-bottom: 0;
  border-radius: 16rpx 16rpx 0 0;
}

.input {
  width: 100%;
  height: 88rpx;
  padding: 0 24rpx 0 76rpx;
  border: none;
  background: transparent;
  font-size: 28rpx;
  color: #172033;
  box-sizing: border-box;
}

.form-actions {
  text-align: right;
  margin-bottom: 34rpx;
}

.link-text {
  color: #1f447a;
  font-size: 26rpx;
  font-weight: 800;
}

.login-btn {
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
  margin-bottom: 34rpx;
  box-shadow: 0 16rpx 30rpx rgba(31, 68, 122, 0.22);
  padding: 0;
}

.login-btn:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.register-link {
  text-align: center;
  font-size: 26rpx;
  color: #667085;
}

.register-link .link-text {
  margin-left: 10rpx;
}
</style>

