<template>
  <view class="create-content-container">
    <view class="header-block">
      <text class="page-title">发布动态</text>
      <text class="page-subtitle">分享校园里的新鲜事，也可以关联一次活动。</text>
    </view>

    <view class="form-panel">
      <view class="form-item">
        <textarea
          v-model="form.content"
          class="textarea"
          placeholder="分享你的动态..."
          maxlength="500"
        />
        <text class="char-count">{{ form.content.length }}/500</text>
      </view>

      <view class="form-item">
        <text class="label">关联活动</text>
        <picker mode="selector" :range="orderPickerLabels" @change="handleOrderChange">
          <view class="picker-view">
            <text :class="form.orderId ? 'picker-text' : 'placeholder'">{{ selectedOrderLabel }}</text>
            <view class="chevron"></view>
          </view>
        </picker>
      </view>

      <view class="form-item">
        <text class="label">图片</text>
        <view class="media-preview" v-if="mediaUrl">
          <image :src="mediaUrl" class="preview-image" mode="aspectFill" />
          <button class="remove-btn" @click="removeMedia">
            <view class="close-icon"></view>
          </button>
        </view>
        <button v-else class="upload-btn" @click="chooseMedia">
          <view class="upload-icon"></view>
          <text>选择图片</text>
        </button>
      </view>
    </view>

    <view class="bottom-actions">
      <button class="ghost-btn" @click="handleCancel">取消</button>
      <button class="submit-btn" :loading="loading" @click="handleSubmit">发布</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useStore } from 'vuex'
import { contentApi, orderApi } from '@/api/index.js'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'
import { ACTIVITY_TYPE_MAP, CAMPUS_MAP } from '@/utils/constants.js'

const store = useStore()

const form = ref({
  content: '',
  mediaType: 'TEXT_ONLY',
  orderId: null
})

const mediaUrl = ref('')
const mediaFilePath = ref('')
const loading = ref(false)
const orderOptions = ref([])
const orderPickerLabels = ref(['不关联活动'])
const selectedOrderLabel = ref('不关联活动')

onLoad(() => {
  if (!store.getters['user/isLogin']) {
    showError('请先登录')
    setTimeout(() => {
      uni.redirectTo({ url: '/pages/auth/login' })
    }, 800)
    return
  }
  loadOrderOptions()
})

const loadOrderOptions = async () => {
  try {
    const result = await orderApi.getOrders({ page: 1, size: 50 })
    orderOptions.value = result.list || []
    orderPickerLabels.value = [
      '不关联活动',
      ...orderOptions.value.map(order => buildOrderLabel(order))
    ]
  } catch (error) {
    orderOptions.value = []
    orderPickerLabels.value = ['不关联活动']
  }
}

const buildOrderLabel = (order) => {
  const type = ACTIVITY_TYPE_MAP[order.activityType] || '活动'
  const campus = CAMPUS_MAP[order.campus] || ''
  const location = order.location || ''
  return [type, campus, location].filter(Boolean).join(' · ')
}

const handleOrderChange = (e) => {
  const index = Number(e.detail.value)
  if (index === 0) {
    form.value.orderId = null
    selectedOrderLabel.value = '不关联活动'
    return
  }
  const order = orderOptions.value[index - 1]
  form.value.orderId = order ? (order.id || order.oid) : null
  selectedOrderLabel.value = orderPickerLabels.value[index]
}

const chooseMedia = () => {
  uni.chooseImage({
    count: 1,
    success: (res) => {
      mediaFilePath.value = res.tempFilePaths[0]
      mediaUrl.value = mediaFilePath.value
      form.value.mediaType = 'IMAGE'
    }
  })
}

const removeMedia = () => {
  mediaUrl.value = ''
  mediaFilePath.value = ''
  form.value.mediaType = 'TEXT_ONLY'
}

const handleCancel = () => {
  uni.navigateBack()
}

const handleSubmit = async () => {
  if (!store.getters['user/isLogin']) {
    showError('请先登录')
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }

  if (!form.value.content.trim()) {
    showError('请输入动态内容')
    return
  }

  loading.value = true
  showLoading('发布中...')

  try {
    const contentId = await contentApi.createContent({
      content: form.value.content.trim(),
      mediaType: form.value.mediaType,
      orderId: form.value.orderId || undefined
    })

    if (contentId && mediaFilePath.value && form.value.mediaType === 'IMAGE') {
      await contentApi.uploadMedia(contentId, mediaFilePath.value)
    }

    hideLoading()
    showSuccess('发布成功')
    setTimeout(() => {
      uni.navigateBack()
    }, 800)
  } catch (error) {
    hideLoading()
    showError(error.message || '发布失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.create-content-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
  padding: 32rpx 28rpx 148rpx;
  box-sizing: border-box;
}

.header-block {
  margin-bottom: 28rpx;
  padding: 32rpx;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(238, 248, 255, 0.72));
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
}

.page-title {
  display: block;
  color: #172033;
  font-size: 42rpx;
  font-weight: 800;
  line-height: 1.2;
}

.page-subtitle {
  display: block;
  margin-top: 12rpx;
  color: #667085;
  font-size: 26rpx;
  line-height: 1.5;
}

.form-panel {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  border-radius: 32rpx;
  padding: 28rpx;
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.24);
  backdrop-filter: blur(24rpx) saturate(1.24);
}

.form-item {
  margin-bottom: 32rpx;
}

.form-item:last-child {
  margin-bottom: 0;
}

.label {
  display: block;
  margin-bottom: 14rpx;
  color: #263244;
  font-size: 27rpx;
  font-weight: 700;
}

.textarea {
  width: 100%;
  min-height: 300rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  border-radius: 26rpx;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.68);
  color: #1f2937;
  font-size: 28rpx;
  line-height: 1.6;
}

.char-count {
  display: block;
  margin-top: 10rpx;
  text-align: right;
  color: #8a94a6;
  font-size: 23rpx;
}

.picker-view {
  min-height: 88rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1rpx solid #d9e0ea;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  border-radius: 22rpx;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.68);
  color: #1f2937;
  font-size: 28rpx;
}

.picker-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.placeholder {
  color: #98a2b3;
}

.chevron {
  width: 16rpx;
  height: 16rpx;
  margin-left: 18rpx;
  border-right: 3rpx solid #98a2b3;
  border-bottom: 3rpx solid #98a2b3;
  transform: rotate(45deg);
}

.media-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 28rpx;
  overflow: hidden;
  background: #eef3f8;
  box-shadow: 0 16rpx 32rpx rgba(22, 47, 84, 0.10);
}

.preview-image {
  width: 100%;
  height: 100%;
}

.remove-btn {
  position: absolute;
  top: 14rpx;
  right: 14rpx;
  width: 58rpx;
  height: 58rpx;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.64);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-icon {
  position: relative;
  width: 26rpx;
  height: 26rpx;
}

.close-icon::before,
.close-icon::after {
  content: "";
  position: absolute;
  left: 12rpx;
  top: 0;
  width: 3rpx;
  height: 26rpx;
  border-radius: 999rpx;
  background: #ffffff;
}

.close-icon::before {
  transform: rotate(45deg);
}

.close-icon::after {
  transform: rotate(-45deg);
}

.upload-btn {
  width: 100%;
  height: 148rpx;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  border: 2rpx dashed rgba(154, 184, 218, 0.80);
  border-radius: 28rpx;
  background:
    radial-gradient(circle at 28% 16%, rgba(255, 255, 255, 0.86), transparent 42%),
    rgba(255, 255, 255, 0.58);
  color: #475467;
  font-size: 28rpx;
}

.upload-icon {
  position: relative;
  width: 36rpx;
  height: 36rpx;
  border: 3rpx solid #1d4ed8;
  border-radius: 8rpx;
  box-sizing: border-box;
}

.upload-icon::before,
.upload-icon::after {
  content: "";
  position: absolute;
  background: #1d4ed8;
  border-radius: 999rpx;
}

.upload-icon::before {
  width: 18rpx;
  height: 3rpx;
  left: 6rpx;
  top: 14rpx;
}

.upload-icon::after {
  width: 3rpx;
  height: 18rpx;
  left: 14rpx;
  top: 6rpx;
}

.bottom-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));
  display: flex;
  gap: 18rpx;
  background: rgba(248, 251, 255, 0.86);
  border-top: 1rpx solid rgba(255, 255, 255, 0.74);
  box-shadow: 0 -12rpx 30rpx rgba(17, 24, 39, 0.08);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.25);
  backdrop-filter: blur(24rpx) saturate(1.25);
}

.ghost-btn,
.submit-btn {
  flex: 1;
  height: 86rpx;
  line-height: 86rpx;
  border: none;
  border-radius: 26rpx;
  padding: 0;
  font-size: 29rpx;
  font-weight: 700;
}

.ghost-btn {
  background: rgba(238, 246, 255, 0.86);
  color: #475467;
}

.submit-btn {
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
  box-shadow: 0 14rpx 28rpx rgba(31, 68, 122, 0.20);
}
</style>
