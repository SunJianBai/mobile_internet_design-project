<template>
  <view class="page">
    <view class="search-bar">
      <input
        v-model="keyword"
        class="search-input"
        placeholder="搜索活动、动态或用户"
        confirm-type="search"
        @confirm="runSearch"
      />
      <button class="search-btn" :disabled="loading" @click="runSearch">
        {{ loading ? '搜索中' : '搜索' }}
      </button>
    </view>

    <view v-if="searched" class="section">
      <view class="section-title">
        <text>活动</text>
        <text class="section-count">{{ orders.length }}</text>
      </view>
      <view v-if="orders.length" class="result-list">
        <view v-for="order in orders" :key="order.oid || order.id" class="result-item" @click="goOrder(order)">
          <text class="result-title">{{ getActivityTypeText(order.activityType) }}</text>
          <text class="result-desc">{{ order.location || '未设置地点' }}</text>
          <text class="result-meta">{{ getCampusText(order.campus) }} · {{ getStatusText(order.status) }}</text>
        </view>
      </view>
      <view v-else class="empty-line">暂无匹配活动</view>
    </view>

    <view v-if="searched" class="section">
      <view class="section-title">
        <text>动态</text>
        <view class="section-actions">
          <text class="section-count">{{ contents.length }}</text>
          <text v-if="keyword.trim()" class="more-link" @click="openContentList">更多</text>
        </view>
      </view>
      <view v-if="contents.length" class="result-list">
        <view
          v-for="content in contents"
          :key="content.pid || content.id"
          class="result-item"
          @click="goContent(content)"
        >
          <text class="result-title">{{ content.user ? content.user.nickname : '匿名用户' }}</text>
          <text class="result-desc">{{ content.content || '暂无内容' }}</text>
          <text class="result-meta">点赞 {{ content.likeCount || 0 }} · 评论 {{ content.commentCount || 0 }}</text>
        </view>
      </view>
      <view v-else class="empty-line">暂无匹配动态</view>
    </view>

    <view v-if="searched" class="section">
      <view class="section-title">
        <text>用户</text>
        <text class="section-count">{{ users.length }}</text>
      </view>
      <view v-if="users.length" class="result-list">
        <view v-for="user in users" :key="user.uid || user.id" class="user-item" @click="toProfile(user)">
          <image v-if="user.avatarUrl" :src="resolveAvatar(user.avatarUrl)" class="user-avatar" mode="aspectFill" />
          <view v-else class="avatar-placeholder">
            <text>{{ getUserInitial(user) }}</text>
          </view>
          <view class="user-main">
            <text class="result-title">{{ user.nickname || '用户' }}</text>
            <text class="result-meta">{{ user.email || user.studentId || '暂无更多信息' }}</text>
          </view>
        </view>
      </view>
      <view v-else class="empty-line">暂无匹配用户</view>
    </view>

    <view v-if="!searched" class="hint">
      <text class="hint-title">CampusHub 搜索</text>
      <text class="hint-text">输入关键词后可以同时查找活动、动态和用户</text>
    </view>
  </view>
</template>

<script>
import { orderApi, contentApi, userApi } from '@/api/index.js'
import { normalizeMediaList, resolveFileUrl } from '@/utils/util.js'
import { ACTIVITY_TYPE_MAP, CAMPUS_MAP, ORDER_STATUS_MAP } from '@/utils/constants.js'
import { goUserProfile } from '@/utils/user-navigation.js'

export default {
  data() {
    return {
      keyword: '',
      loading: false,
      searched: false,
      orders: [],
      contents: [],
      users: []
    }
  },
  onLoad(options) {
    if (options && options.keyword) {
      this.keyword = decodeURIComponent(options.keyword)
      this.runSearch()
    }
  },
  methods: {
    normalizePage(result) {
      if (Array.isArray(result)) return result
      if (Array.isArray(result?.list)) return result.list
      if (Array.isArray(result?.records)) return result.records
      return []
    },
    async runSearch() {
      const kw = this.keyword.trim()
      if (!kw) {
        uni.showToast({ title: '请输入关键词', icon: 'none' })
        return
      }

      this.loading = true
      this.searched = true

      const [orders, contents, users] = await Promise.all([
        this.searchOrders(kw),
        this.searchContents(kw),
        this.searchUsers(kw)
      ])

      this.orders = orders
      this.contents = contents
      this.users = users
      this.loading = false
    },
    async searchOrders(keyword) {
      try {
        const result = await orderApi.getOrders({ page: 1, size: 50 })
        const source = this.normalizePage(result)
        const lower = keyword.toLowerCase()
        return source.filter(order => {
          const fields = [
            order.location,
            order.description,
            order.remark,
            order.user && order.user.nickname,
            this.getActivityTypeText(order.activityType),
            this.getCampusText(order.campus),
            this.getStatusText(order.status)
          ]
          return fields.some(value => String(value || '').toLowerCase().includes(lower))
        }).slice(0, 10)
      } catch (error) {
        console.error('搜索活动失败:', error)
        return []
      }
    },
    async searchContents(keyword) {
      try {
        const result = await contentApi.searchByKeyword(keyword, 1, 10)
        return this.normalizePage(result).map(item => ({
          ...item,
          media: normalizeMediaList(item)
        }))
      } catch (error) {
        console.error('搜索动态失败:', error)
        return []
      }
    },
    async searchUsers(keyword) {
      try {
        const result = await userApi.searchUsers(keyword, 1, 10)
        return this.normalizePage(result)
      } catch (error) {
        console.error('搜索用户失败:', error)
        return []
      }
    },
    goOrder(order) {
      const id = order.oid || order.id
      if (id) {
        uni.navigateTo({ url: `/pages/order/detail?id=${id}` })
      }
    },
    goContent(content) {
      const id = content.pid || content.id
      if (id) {
        uni.navigateTo({ url: `/pages/content/detail?id=${id}` })
      }
    },
    openContentList() {
      uni.setStorageSync('contentListFilter', { mode: 'all', keyword: this.keyword.trim() })
      uni.switchTab({ url: '/pages/content/list' })
    },
    resolveAvatar(url) {
      return resolveFileUrl(url)
    },
    toProfile(user) {
      goUserProfile(user)
    },
    getUserInitial(user) {
      return (user && user.nickname ? user.nickname.slice(0, 1) : '用')
    },
    getActivityTypeText(type) {
      return ACTIVITY_TYPE_MAP[type] || '其他'
    },
    getCampusText(campus) {
      return CAMPUS_MAP[campus] || '其他校区'
    },
    getStatusText(status) {
      return ORDER_STATUS_MAP[status] || '未知'
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
  padding: 28rpx;
  box-sizing: border-box;
}

.search-bar {
  display: flex;
  gap: 16rpx;
  margin-bottom: 28rpx;
  padding: 14rpx;
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

.search-input {
  flex: 1;
  height: 76rpx;
  padding: 0 24rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.66);
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  font-size: 28rpx;
}

.search-btn {
  width: 132rpx;
  height: 76rpx;
  border: none;
  border-radius: 22rpx;
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
  font-size: 28rpx;
  line-height: 76rpx;
  padding: 0;
}

.search-btn[disabled] {
  background: #c7d2df;
}

.section {
  margin-bottom: 26rpx;
  padding: 26rpx;
  border-radius: 30rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
  color: #172033;
  font-size: 30rpx;
  font-weight: 850;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.section-count {
  color: #8a94a6;
  font-size: 24rpx;
  font-weight: normal;
}

.more-link {
  color: #1f447a;
  font-size: 24rpx;
  font-weight: normal;
}

.result-list {
  display: flex;
  flex-direction: column;
}

.result-item,
.user-item {
  margin-top: 14rpx;
  padding: 20rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.58);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
}

.result-title {
  display: block;
  margin-bottom: 8rpx;
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.result-desc {
  display: block;
  margin-bottom: 8rpx;
  color: #475467;
  font-size: 26rpx;
  line-height: 1.5;
}

.result-meta {
  display: block;
  color: #8a94a6;
  font-size: 24rpx;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.user-avatar,
.avatar-placeholder {
  width: 76rpx;
  height: 76rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 30% 18%, rgba(255, 255, 255, 0.92), transparent 42%),
    linear-gradient(145deg, rgba(237, 247, 255, 0.96), rgba(210, 231, 255, 0.78));
  color: #1f447a;
  font-size: 30rpx;
}

.user-main {
  flex: 1;
  min-width: 0;
}

.empty-line {
  padding: 26rpx 0;
  color: #8a94a6;
  font-size: 26rpx;
  text-align: center;
}

.hint {
  min-height: 520rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  color: #8a94a6;
  margin-top: 40rpx;
  border-radius: 34rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.82), rgba(244, 250, 255, 0.64));
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.08),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.90);
}

.hint-title {
  color: #172033;
  font-size: 34rpx;
  font-weight: 850;
}

.hint-text {
  color: #8a94a6;
  font-size: 26rpx;
}
</style>
