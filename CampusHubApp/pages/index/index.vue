<template>
  <view class="container">
    <view class="app-top home-top">
      <view class="hero-row">
        <view class="hero-copy">
          <text class="eyebrow">校内活动预约与分享平台</text>
          <text class="brand">CampusHub</text>
          <text class="hero-subtitle">{{ welcomeText }}</text>
        </view>
        <view class="avatar-box" @click="toUser">
          <image v-if="avatarSrc" :src="avatarSrc" class="avatar" mode="aspectFill" />
          <view v-else class="avatar-placeholder">
            <text>{{ userInitial }}</text>
          </view>
        </view>
      </view>

      <view class="hero-actions">
        <view class="hero-action" @click="toCreateOrder">
          <view class="hero-action-icon order-icon">
            <view class="order-line"></view>
            <view class="order-dots"><view></view><view></view><view></view></view>
          </view>
          <text>发起活动</text>
        </view>
        <view class="hero-action" @click="toCreateContent">
          <view class="hero-action-icon content-icon">
            <view class="content-bubble"></view>
            <view class="content-line wide"></view>
            <view class="content-line"></view>
          </view>
          <text>发布动态</text>
        </view>
        <view class="hero-action" @click="toAIChat">
          <view class="hero-action-icon ai-icon">
            <text>AI</text>
          </view>
          <text>AI助手</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-title">
        <view>
          <text class="section-heading">{{ orderSectionTitle }}</text>
          <text class="section-desc">{{ orderSectionDesc }}</text>
        </view>
        <text class="more" @click="openOrderSection">全部</text>
      </view>

      <view v-if="primaryOrders.length > 0" class="order-list">
        <view
          v-for="order in primaryOrders"
          :key="order.oid || order.id"
          class="order-item"
          @click="toOrderDetail(order.oid || order.id)"
        >
          <view class="order-mark">
            <text>{{ getActivityType(order.activityType).slice(0, 1) }}</text>
          </view>
          <view class="order-main">
            <view class="order-head">
              <text class="order-type">{{ getActivityType(order.activityType) }}</text>
              <text class="status-pill" :class="`status-${order.status || 'UNKNOWN'}`">{{ getStatus(order.status) }}</text>
            </view>
            <text class="order-location">{{ order.location || '未设置地点' }}</text>
            <view class="order-bottom">
              <text>{{ formatTime(order.startTime, 'MM-DD HH:mm') }}</text>
              <text>{{ order.currentPeople || 0 }}/{{ order.maxPeople || 0 }} 人</text>
              <text>{{ getCampus(order.campus) }}</text>
            </view>
          </view>
        </view>
      </view>
      <view v-else class="empty-card" @click="toCreateOrder">
        <text class="empty-title">{{ orderEmptyTitle }}</text>
        <text class="empty-text">{{ orderEmptyText }}</text>
      </view>
    </view>

    <view class="section">
      <view class="section-title">
        <view>
          <text class="section-heading">{{ contentSectionTitle }}</text>
          <text class="section-desc">{{ contentSectionDesc }}</text>
        </view>
        <text class="more" @click="openContentSection">全部</text>
      </view>

      <view v-if="primaryContents.length > 0" class="content-list">
        <view
          v-for="content in primaryContents"
          :key="content.pid || content.id"
          class="content-item"
          @click="toContentDetail(content.pid || content.id)"
        >
          <view class="content-main">
            <view class="content-header">
              <image
                v-if="content.user && content.user.avatarUrl"
                :src="content.user.avatarUrl"
                class="user-avatar"
                mode="aspectFill"
                @click.stop="toProfile(content.user)"
              />
              <view v-else class="small-avatar" @click.stop="toProfile(content.user)">
                <text>{{ getUserInitial(content.user) }}</text>
              </view>
              <view class="user-info">
                <text class="user-name" @click.stop="toProfile(content.user)">{{ content.user ? content.user.nickname : '匿名用户' }}</text>
                <text class="content-time">{{ formatRelativeTime(content.createdAt) }}</text>
              </view>
            </view>
            <text class="content-text">{{ content.content || '暂无内容' }}</text>
            <view class="content-footer">
              <view class="count-chip"><text>赞 {{ content.likeCount || 0 }}</text></view>
              <view class="count-chip"><text>评 {{ content.commentCount || 0 }}</text></view>
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
      <view v-else class="empty-card" @click="toCreateContent">
        <text class="empty-title">{{ contentEmptyTitle }}</text>
        <text class="empty-text">{{ contentEmptyText }}</text>
      </view>
    </view>

    <view v-if="isLogin && campusOrders.length > 0" class="section compact-section">
      <view class="section-title">
        <view>
          <text class="section-heading">校园正在发生</text>
          <text class="section-desc">看看同学们最近发起的活动</text>
        </view>
        <text class="more" @click="toOrderList">更多</text>
      </view>
      <scroll-view scroll-x class="campus-strip" show-scrollbar="false">
        <view class="campus-scroll">
          <view
            v-for="order in campusOrders"
            :key="order.oid || order.id"
            class="campus-card"
            @click="toOrderDetail(order.oid || order.id)"
          >
            <text class="campus-type">{{ getActivityType(order.activityType) }}</text>
            <text class="campus-location">{{ order.location || '未设置地点' }}</text>
            <text class="campus-meta">{{ formatTime(order.startTime, 'MM-DD HH:mm') }}</text>
          </view>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script>
import { orderApi, contentApi } from '@/api/index.js'
import { formatTime, formatRelativeTime, normalizeMediaList, resolveFileUrl } from '@/utils/util.js'
import { ACTIVITY_TYPE_MAP, ORDER_STATUS_MAP, CAMPUS_MAP } from '@/utils/constants.js'
import { goUserProfile } from '@/utils/user-navigation.js'

export default {
  data() {
    return {
      myOrders: [],
      campusOrders: [],
      myContents: [],
      campusContents: [],
      loading: false
    }
  },
  computed: {
    userInfo() {
      return this.$store.getters['user/userInfo']
    },
    isLogin() {
      return this.$store.getters['user/isLogin'] || !!uni.getStorageSync('userId')
    },
    currentUserId() {
      return String(this.$store.getters['user/userId'] || uni.getStorageSync('userId') || '')
    },
    avatarSrc() {
      return this.userInfo && this.userInfo.avatarUrl ? resolveFileUrl(this.userInfo.avatarUrl) : ''
    },
    userInitial() {
      return this.userInfo && this.userInfo.nickname ? this.userInfo.nickname.slice(0, 1) : '我'
    },
    welcomeText() {
      return this.isLogin
        ? `欢迎回来，${this.userInfo?.nickname || '同学'}`
        : '登录后可以管理你的活动与动态'
    },
    primaryOrders() {
      return this.isLogin ? this.myOrders : this.campusOrders
    },
    primaryContents() {
      return this.isLogin ? this.myContents : this.campusContents
    },
    orderSectionTitle() {
      return this.isLogin ? '我发布的活动' : '校园活动'
    },
    orderSectionDesc() {
      return this.isLogin ? '最近创建的预约订单' : '发现正在等待加入的活动'
    },
    orderEmptyTitle() {
      return this.isLogin ? '还没有发起活动' : '暂无活动'
    },
    orderEmptyText() {
      return this.isLogin ? '点这里发起一次新的校园活动。' : '登录后可以发起活动并查看自己的记录。'
    },
    contentSectionTitle() {
      return this.isLogin ? '我发布的动态' : '校园动态'
    },
    contentSectionDesc() {
      return this.isLogin ? '你最近分享的校园片段' : '同学们正在分享的新鲜事'
    },
    contentEmptyTitle() {
      return this.isLogin ? '还没有发布动态' : '暂无动态'
    },
    contentEmptyText() {
      return this.isLogin ? '点这里记录一次校园瞬间。' : '登录后可以发布动态并关联活动。'
    }
  },
  onLoad() {
    this.$store.dispatch('user/initUserState')
    this.loadData()
  },
  onShow() {
    this.loadData()
  },
  onPullDownRefresh() {
    this.loadData().finally(() => {
      uni.stopPullDownRefresh()
    })
  },
  methods: {
    normalizePage(result) {
      if (Array.isArray(result)) return result
      if (Array.isArray(result?.list)) return result.list
      if (Array.isArray(result?.records)) return result.records
      return []
    },
    normalizeContents(list) {
      return list.map(item => ({
        ...item,
        user: item.user ? {
          ...item.user,
          avatarUrl: resolveFileUrl(item.user.avatarUrl)
        } : item.user,
        media: normalizeMediaList(item)
      }))
    },
    isMineContent(content) {
      const ownerId = content.user && (content.user.id || content.user.uid)
      return String(ownerId || '') === this.currentUserId
    },
    async loadData() {
      if (this.loading) return
      this.loading = true
      try {
        const requests = [
          orderApi.getOrders({ page: 1, size: 6 }).catch(() => ({ list: [] })),
          contentApi.getContents({ page: 1, size: 30 }).catch(() => ({ list: [] }))
        ]
        if (this.isLogin) {
          requests.push(orderApi.getMyOrders(1, 6).catch(() => ({ list: [] })))
        }

        const [ordersRes, contentsRes, myOrdersRes] = await Promise.all(requests)
        this.campusOrders = this.normalizePage(ordersRes).slice(0, 5)

        const contents = this.normalizeContents(this.normalizePage(contentsRes))
        this.campusContents = contents.slice(0, 5)
        this.myContents = this.isLogin ? contents.filter(this.isMineContent).slice(0, 5) : []
        this.myOrders = this.isLogin ? this.normalizePage(myOrdersRes).slice(0, 5) : []
      } catch (error) {
        console.error('加载首页数据失败:', error)
        this.myOrders = []
        this.campusOrders = []
        this.myContents = []
        this.campusContents = []
      } finally {
        this.loading = false
      }
    },
    getActivityType(type) {
      return ACTIVITY_TYPE_MAP[type] || '其他'
    },
    getStatus(status) {
      return ORDER_STATUS_MAP[status] || '未知'
    },
    getCampus(campus) {
      return CAMPUS_MAP[campus] || '其他校区'
    },
    getUserInitial(user) {
      return user && user.nickname ? user.nickname.slice(0, 1) : '用'
    },
    formatTime,
    formatRelativeTime,
    toUser() {
      if (!this.isLogin) {
        uni.navigateTo({ url: '/pages/auth/login' })
      } else {
        uni.switchTab({ url: '/pages/user/info' })
      }
    },
    requireLoginThen(callback) {
      if (!this.isLogin) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }
      callback()
    },
    toOrderList() {
      uni.setStorageSync('orderListFilter', { mode: 'all' })
      uni.switchTab({ url: '/pages/order/list' })
    },
    toContentList() {
      uni.setStorageSync('contentListFilter', { mode: 'all', keyword: '' })
      uni.switchTab({ url: '/pages/content/list' })
    },
    openOrderSection() {
      uni.setStorageSync('orderListFilter', { mode: this.isLogin ? 'mine' : 'all' })
      uni.switchTab({ url: '/pages/order/list' })
    },
    openContentSection() {
      uni.setStorageSync('contentListFilter', { mode: this.isLogin ? 'mine' : 'all', keyword: '' })
      uni.switchTab({ url: '/pages/content/list' })
    },
    toCreateOrder() {
      this.requireLoginThen(() => {
        uni.navigateTo({ url: '/pages/order/create' })
      })
    },
    toCreateContent() {
      this.requireLoginThen(() => {
        uni.navigateTo({ url: '/pages/content/create' })
      })
    },
    toAIChat() {
      uni.navigateTo({ url: '/pages/ai/chat' })
    },
    toOrderDetail(orderId) {
      if (!orderId) return
      uni.navigateTo({ url: `/pages/order/detail?id=${orderId}` })
    },
    toContentDetail(contentId) {
      if (!contentId) return
      uni.navigateTo({ url: `/pages/content/detail?id=${contentId}` })
    },
    toProfile(user) {
      goUserProfile(user)
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  padding-bottom: 152rpx;
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 8%, rgba(24, 196, 214, 0.10), transparent 28%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 48%, #f8fbff 100%);
}

.home-top {
  padding: 44rpx 30rpx 74rpx;
  color: #ffffff;
}

.hero-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 26rpx;
}

.hero-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.eyebrow {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.72);
}

.brand {
  font-size: 52rpx;
  line-height: 1.08;
  font-weight: 850;
}

.hero-subtitle {
  font-size: 25rpx;
  color: rgba(255, 255, 255, 0.86);
}

.avatar-box {
  width: 86rpx;
  height: 86rpx;
  border-radius: 50%;
  overflow: hidden;
  border: 4rpx solid rgba(255, 255, 255, 0.30);
  background: rgba(255, 255, 255, 0.18);
  flex: 0 0 86rpx;
}

.avatar,
.avatar-placeholder {
  width: 100%;
  height: 100%;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 800;
}

.hero-actions {
  margin-top: 30rpx;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
}

.hero-action {
  min-height: 132rpx;
  padding: 18rpx 12rpx;
  border-radius: 28rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.28);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.23), rgba(255, 255, 255, 0.08));
  box-shadow:
    0 14rpx 30rpx rgba(8, 29, 61, 0.14),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.34);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  -webkit-backdrop-filter: blur(20rpx) saturate(1.2);
  backdrop-filter: blur(20rpx) saturate(1.2);
}

.hero-action:active {
  transform: scale(0.97);
  opacity: 0.88;
}

.hero-action text {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 750;
  white-space: nowrap;
}

.hero-action-icon {
  position: relative;
  width: 58rpx;
  height: 58rpx;
  border-radius: 20rpx;
  background:
    radial-gradient(circle at 30% 18%, rgba(255, 255, 255, 0.95), transparent 44%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.88), rgba(213, 235, 255, 0.62));
  color: #1f447a;
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.88);
}

.order-line {
  position: absolute;
  left: 14rpx;
  top: 14rpx;
  width: 30rpx;
  height: 26rpx;
  border: 3rpx solid currentColor;
  border-top-width: 8rpx;
  border-radius: 9rpx;
  box-sizing: border-box;
}

.order-dots {
  position: absolute;
  left: 19rpx;
  top: 33rpx;
  display: flex;
  gap: 4rpx;
}

.order-dots view {
  width: 5rpx;
  height: 5rpx;
  border-radius: 50%;
  background: currentColor;
}

.content-bubble {
  position: absolute;
  left: 13rpx;
  top: 15rpx;
  width: 34rpx;
  height: 26rpx;
  border: 3rpx solid currentColor;
  border-radius: 13rpx;
  box-sizing: border-box;
}

.content-bubble::after {
  content: "";
  position: absolute;
  left: 5rpx;
  bottom: -8rpx;
  width: 10rpx;
  height: 10rpx;
  border-left: 3rpx solid currentColor;
  border-bottom: 3rpx solid currentColor;
  transform: skew(-18deg);
}

.content-line {
  position: absolute;
  left: 22rpx;
  top: 29rpx;
  width: 15rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: currentColor;
}

.content-line.wide {
  top: 22rpx;
  width: 20rpx;
}

.ai-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-icon text {
  color: #1f447a;
  font-size: 24rpx;
  font-weight: 850;
}

.section {
  margin: -36rpx 30rpx 54rpx;
  padding: 26rpx;
  border-radius: 30rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.24);
  backdrop-filter: blur(24rpx) saturate(1.24);
}

.section + .section {
  margin-top: 18rpx;
}

.compact-section {
  margin-bottom: 34rpx;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 22rpx;
  gap: 18rpx;
}

.section-title view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.section-heading {
  font-size: 32rpx;
  line-height: 1.2;
  font-weight: 850;
  color: #172033;
}

.section-desc {
  font-size: 22rpx;
  color: #8a94a6;
}

.more {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  color: #1f447a;
  background: rgba(237, 247, 255, 0.78);
  font-size: 24rpx;
  font-weight: 750;
}

.order-list,
.content-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.order-item {
  display: flex;
  gap: 16rpx;
  padding: 20rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
}

.order-mark {
  width: 62rpx;
  height: 62rpx;
  flex: 0 0 62rpx;
  border-radius: 20rpx;
  background:
    radial-gradient(circle at 30% 18%, rgba(255, 255, 255, 0.92), transparent 42%),
    linear-gradient(145deg, rgba(237, 247, 255, 0.96), rgba(210, 231, 255, 0.78));
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 850;
}

.order-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.order-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.order-type {
  flex: 1;
  min-width: 0;
  font-size: 29rpx;
  font-weight: 850;
  color: #172033;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  padding: 7rpx 14rpx;
  border-radius: 999rpx;
  color: #1f447a;
  background: #edf4ff;
  font-size: 21rpx;
  font-weight: 750;
  white-space: nowrap;
}

.status-COMPLETED,
.status-IN_PROGRESS {
  color: #087443;
  background: #e8f7ef;
}

.status-CANCELLED,
.status-EXPIRED {
  color: #b42318;
  background: #fff1f0;
}

.order-location,
.order-bottom {
  color: #667085;
  font-size: 23rpx;
}

.order-location {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order-bottom {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.content-item {
  display: flex;
  gap: 18rpx;
  padding: 20rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
}

.content-main {
  flex: 1;
  min-width: 0;
}

.content-header {
  display: flex;
  align-items: center;
  margin-bottom: 14rpx;
}

.user-avatar,
.small-avatar {
  width: 54rpx;
  height: 54rpx;
  border-radius: 50%;
  margin-right: 14rpx;
  flex-shrink: 0;
}

.small-avatar {
  background: #edf4ff;
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 800;
}

.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 26rpx;
  font-weight: 800;
  color: #172033;
}

.content-time {
  font-size: 22rpx;
  color: #8a94a6;
  margin-top: 4rpx;
}

.content-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 27rpx;
  color: #344054;
  line-height: 1.6;
}

.content-thumb {
  width: 126rpx;
  height: 126rpx;
  border-radius: 24rpx;
  background: #eef1f5;
  flex-shrink: 0;
}

.content-footer {
  display: flex;
  gap: 12rpx;
  margin-top: 14rpx;
}

.count-chip {
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.74);
  color: #667085;
  font-size: 22rpx;
}

.empty-card {
  padding: 36rpx 28rpx;
  border-radius: 26rpx;
  border: 1rpx dashed rgba(31, 68, 122, 0.20);
  background: rgba(255, 255, 255, 0.52);
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.empty-title {
  color: #172033;
  font-size: 29rpx;
  font-weight: 850;
}

.empty-text {
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}

.campus-strip {
  width: 100%;
  white-space: nowrap;
}

.campus-scroll {
  display: inline-flex;
  gap: 16rpx;
  padding-bottom: 2rpx;
}

.campus-card {
  width: 252rpx;
  padding: 20rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
  display: inline-flex;
  flex-direction: column;
  gap: 8rpx;
  box-sizing: border-box;
}

.campus-type {
  color: #172033;
  font-size: 28rpx;
  font-weight: 850;
}

.campus-location,
.campus-meta {
  color: #667085;
  font-size: 23rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
