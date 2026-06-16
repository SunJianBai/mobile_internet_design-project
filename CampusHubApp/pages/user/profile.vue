<template>
  <view class="profile-container">
    <view v-if="user" class="profile-content">
      <view class="hero-card">
        <view class="avatar-shell">
          <image v-if="avatarUrl" :src="avatarUrl" class="avatar" mode="aspectFill" />
          <view v-else class="avatar-placeholder">{{ userInitial }}</view>
        </view>
        <view class="hero-main">
          <text class="nickname">{{ user.nickname || '用户' }}</text>
          <text v-if="user.email" class="email">{{ user.email }}</text>
          <text class="signature">{{ user.signature || '这个同学还没有填写个性签名' }}</text>
        </view>
      </view>

      <view class="overview-card">
        <view class="overview-item">
          <text class="overview-num">{{ userOrders.length }}</text>
          <text class="overview-label">发布活动</text>
        </view>
        <view class="overview-item">
          <text class="overview-num">{{ userContents.length }}</text>
          <text class="overview-label">校园动态</text>
        </view>
        <view class="overview-item">
          <text class="overview-num">{{ joinText }}</text>
          <text class="overview-label">加入时间</text>
        </view>
      </view>

      <view class="section">
        <view class="section-title">
          <view>
            <text class="section-heading">TA 的活动</text>
            <text class="section-desc">最近发起的校园预约</text>
          </view>
        </view>
        <view v-if="userOrders.length" class="order-list">
          <view
            v-for="order in userOrders"
            :key="order.oid || order.id"
            class="order-item"
            @click="toOrderDetail(order.oid || order.id)"
          >
            <text class="order-type">{{ getActivityType(order.activityType) }}</text>
            <text class="order-location">{{ order.location || '未设置地点' }}</text>
            <view class="order-meta">
              <text>{{ formatDisplayTime(order.startTime) }}</text>
              <text>{{ order.currentPeople || 0 }}/{{ order.maxPeople || 0 }} 人</text>
              <text>{{ getCampus(order.campus) }}</text>
            </view>
          </view>
        </view>
        <view v-else class="empty-line">暂无公开活动</view>
      </view>

      <view class="section">
        <view class="section-title">
          <view>
            <text class="section-heading">TA 的动态</text>
            <text class="section-desc">最近分享的校园片段</text>
          </view>
        </view>
        <view v-if="userContents.length" class="content-list">
          <view
            v-for="content in userContents"
            :key="content.pid || content.id"
            class="content-item"
            @click="toContentDetail(content.pid || content.id)"
          >
            <view class="content-main">
              <text class="content-text">{{ content.content || '暂无内容' }}</text>
              <view class="content-meta">
                <text>{{ formatRelativeTime(content.createdAt) }}</text>
                <text>赞 {{ content.likeCount || 0 }}</text>
                <text>评 {{ content.commentCount || 0 }}</text>
              </view>
            </view>
            <image
              v-if="content.media && content.media.length"
              :src="content.media[0].url"
              class="content-thumb"
              mode="aspectFill"
            />
          </view>
        </view>
        <view v-else class="empty-line">暂无公开动态</view>
      </view>
    </view>

    <view v-else class="loading-card">
      <text>{{ loading ? '加载中...' : '用户不存在' }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { userApi, orderApi, contentApi } from '@/api/index.js'
import { resolveFileUrl, normalizeMediaList, formatRelativeTime, formatTime, showError } from '@/utils/util.js'
import { ACTIVITY_TYPE_MAP, CAMPUS_MAP } from '@/utils/constants.js'

const user = ref(null)
const userId = ref('')
const userOrders = ref([])
const userContents = ref([])
const loading = ref(false)

const avatarUrl = computed(() => user.value?.avatarUrl ? resolveFileUrl(user.value.avatarUrl) : '')
const userInitial = computed(() => String(user.value?.nickname || '用').slice(0, 1))
const joinText = computed(() => {
  if (!user.value?.createdAt) return '--'
  return formatTime(user.value.createdAt, 'YYYY-MM')
})

const normalizePage = (result) => {
  if (Array.isArray(result)) return result
  if (Array.isArray(result?.list)) return result.list
  if (Array.isArray(result?.records)) return result.records
  return []
}

const getOwnerId = (item) => {
  return item?.user ? (item.user.id || item.user.uid || item.user.userId) : ''
}

const loadProfile = async () => {
  if (!userId.value) {
    showError('缺少用户 ID')
    return
  }

  loading.value = true
  try {
    const [userInfo, ordersRes, contentsRes] = await Promise.all([
      userApi.getUserInfo(userId.value),
      orderApi.getOrders({ page: 1, size: 50 }).catch(() => ({ list: [] })),
      contentApi.getContents({ page: 1, size: 50 }).catch(() => ({ list: [] }))
    ])

    user.value = userInfo
    userOrders.value = normalizePage(ordersRes)
      .filter(order => String(getOwnerId(order)) === String(userId.value))
      .slice(0, 5)
    userContents.value = normalizePage(contentsRes)
      .filter(content => String(getOwnerId(content)) === String(userId.value))
      .map(item => ({
        ...item,
        media: normalizeMediaList(item)
      }))
      .slice(0, 5)
  } catch (error) {
    showError(error.message || '加载用户失败')
  } finally {
    loading.value = false
  }
}

const getActivityType = (type) => ACTIVITY_TYPE_MAP[type] || '其他'
const getCampus = (campus) => CAMPUS_MAP[campus] || '其他校区'
const formatDisplayTime = (time) => time ? formatTime(time, 'MM-DD HH:mm') : '未设置'

const toOrderDetail = (id) => {
  if (!id) return
  uni.navigateTo({ url: `/pages/order/detail?id=${id}` })
}

const toContentDetail = (id) => {
  if (!id) return
  uni.navigateTo({ url: `/pages/content/detail?id=${id}` })
}

onLoad((options = {}) => {
  userId.value = options.id || ''
  loadProfile()
})
</script>

<style scoped>
.profile-container {
  min-height: 100vh;
  padding: 30rpx 28rpx 54rpx;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
}

.hero-card,
.overview-card,
.section,
.loading-card {
  border-radius: 34rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.70);
  background:
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.74), transparent 34%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.86), rgba(244, 250, 255, 0.62));
  box-shadow:
    0 22rpx 48rpx rgba(22, 47, 84, 0.12),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.92),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.46);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.45);
  backdrop-filter: blur(24rpx) saturate(1.45);
}

.hero-card {
  display: flex;
  align-items: center;
  gap: 22rpx;
  padding: 30rpx;
}

.avatar-shell {
  width: 132rpx;
  height: 132rpx;
  border-radius: 50%;
  padding: 8rpx;
  background: rgba(255, 255, 255, 0.58);
  box-shadow:
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.82),
    0 16rpx 32rpx rgba(22, 47, 84, 0.12);
  box-sizing: border-box;
  flex: 0 0 132rpx;
}

.avatar,
.avatar-placeholder {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
  font-size: 46rpx;
  font-weight: 900;
}

.hero-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.nickname {
  color: #172033;
  font-size: 40rpx;
  font-weight: 900;
}

.email,
.signature {
  color: #667085;
  font-size: 25rpx;
  line-height: 1.45;
  word-break: break-word;
}

.overview-card {
  padding: 22rpx;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
}

.overview-item {
  min-height: 112rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.58);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8rpx;
}

.overview-num {
  color: #1f447a;
  font-size: 34rpx;
  font-weight: 900;
}

.overview-label {
  color: #667085;
  font-size: 22rpx;
}

.section {
  padding: 26rpx;
}

.section-title {
  margin-bottom: 18rpx;
}

.section-title view {
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.section-heading {
  color: #172033;
  font-size: 31rpx;
  font-weight: 900;
}

.section-desc {
  color: #8a94a6;
  font-size: 23rpx;
}

.order-list,
.content-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.order-item,
.content-item {
  padding: 20rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.60);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
}

.order-type {
  color: #172033;
  font-size: 29rpx;
  font-weight: 900;
}

.order-location {
  display: block;
  margin-top: 6rpx;
  color: #667085;
  font-size: 24rpx;
}

.order-meta,
.content-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 12rpx;
  color: #667085;
  font-size: 23rpx;
}

.content-item {
  display: flex;
  gap: 16rpx;
}

.content-main {
  flex: 1;
  min-width: 0;
}

.content-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: #344054;
  font-size: 27rpx;
  line-height: 1.55;
}

.content-thumb {
  width: 112rpx;
  height: 112rpx;
  border-radius: 22rpx;
  flex: 0 0 112rpx;
}

.empty-line,
.loading-card {
  padding: 56rpx 20rpx;
  color: #8a94a6;
  font-size: 26rpx;
  text-align: center;
}
</style>
