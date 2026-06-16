<template>
  <view class="edit-container">
    <view class="page-header">
      <text class="page-title">编辑资料</text>
      <text class="page-subtitle">更新昵称和个性签名，让同学更容易认识你。</text>
    </view>

    <view class="form glass-panel">
      <view class="form-item">
        <text class="label">昵称</text>
        <view class="input-wrap user-icon">
          <input v-model="form.nickname" class="input" placeholder="请输入昵称" />
        </view>
      </view>

      <view class="form-item">
        <text class="label">个性签名</text>
        <view class="textarea-wrap note-icon">
          <textarea
            v-model="form.signature"
            class="textarea"
            placeholder="写一句校园状态、兴趣或自我介绍"
            maxlength="100"
          />
        </view>
        <text class="counter">{{ form.signature.length }}/100</text>
      </view>

      <button class="submit-btn" :loading="loading" @click="handleSubmit">保存</button>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'

const store = useStore()

const form = ref({
  nickname: '',
  signature: ''
})

const loading = ref(false)

onMounted(() => {
  const userInfo = store.getters['user/userInfo']
  if (userInfo) {
    form.value.nickname = userInfo.nickname || ''
    form.value.signature = userInfo.signature || ''
  }
})

const handleSubmit = async () => {
  if (!form.value.nickname.trim()) {
    showError('请输入昵称')
    return
  }
  
  loading.value = true
  showLoading('保存中...')
  
  try {
    await store.dispatch('user/updateUserInfo', {
      nickname: form.value.nickname,
      signature: form.value.signature
    })
    showSuccess('保存成功')
    
    setTimeout(() => {
      uni.navigateBack()
    }, 1000)
  } catch (error) {
    showError(error.message || '保存失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}
</script>

<style scoped>
.edit-container {
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
  margin-bottom: 32rpx;
}

.label {
  display: block;
  font-size: 28rpx;
  font-weight: 800;
  color: #263244;
  margin-bottom: 16rpx;
}

.input-wrap,
.textarea-wrap {
  position: relative;
  border-radius: 26rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  background: rgba(255, 255, 255, 0.64);
  box-shadow:
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.82),
    inset -1rpx -1rpx 1rpx rgba(255, 255, 255, 0.42);
}

.input-wrap {
  min-height: 88rpx;
  display: flex;
  align-items: center;
}

.input-wrap::before,
.input-wrap::after,
.textarea-wrap::before,
.textarea-wrap::after {
  content: "";
  position: absolute;
  left: 24rpx;
  box-sizing: border-box;
  color: #1f447a;
  pointer-events: none;
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

.note-icon::before {
  width: 32rpx;
  height: 32rpx;
  top: 25rpx;
  border: 3rpx solid currentColor;
  border-radius: 8rpx;
}

.note-icon::after {
  width: 18rpx;
  height: 3rpx;
  top: 36rpx;
  left: 31rpx;
  border-radius: 999rpx;
  background: currentColor;
  box-shadow: 0 12rpx 0 currentColor;
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

.textarea {
  width: 100%;
  min-height: 210rpx;
  padding: 24rpx 24rpx 24rpx 76rpx;
  border: none;
  background: transparent;
  font-size: 28rpx;
  line-height: 1.6;
  color: #172033;
  box-sizing: border-box;
}

.counter {
  display: block;
  margin-top: 10rpx;
  text-align: right;
  color: #8a94a6;
  font-size: 23rpx;
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

