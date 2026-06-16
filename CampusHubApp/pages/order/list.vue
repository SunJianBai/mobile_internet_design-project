<template>
  <view class="page">
    <view class="app-top">
      <view class="title-row">
        <view>
          <text class="page-title">预约订单</text>
          <text class="page-subtitle">{{ hasActiveFilter ? filterSummary : '发现正在等待加入的校园活动' }}</text>
        </view>
      </view>
    </view>

    <view class="filter-card">
      <view class="filter-grid">
        <picker mode="selector" :range="typeOptions" range-key="label" @change="onTypeChange">
          <view class="filter-item">
            <text>{{ selectedType ? selectedType.label : '活动类型' }}</text>
            <view class="chevron"></view>
          </view>
        </picker>
        <picker mode="selector" :range="campusOptions" range-key="label" @change="onCampusChange">
          <view class="filter-item">
            <text>{{ selectedCampus ? selectedCampus.label : '校区' }}</text>
            <view class="chevron"></view>
          </view>
        </picker>
        <picker mode="selector" :range="statusOptions" range-key="label" @change="onStatusChange">
          <view class="filter-item">
            <text>{{ selectedStatus ? selectedStatus.label : '状态' }}</text>
            <view class="chevron"></view>
          </view>
        </picker>
      </view>
      <view class="filter-bottom">
        <view class="filter-toggle" :class="{ active: onlyMine }" @click="toggleOnlyMine">
          <view class="toggle-dot"></view>
          <text>我发布的</text>
        </view>
        <text v-if="hasActiveFilter" class="mode-clear" @click="clearMode">重置筛选</text>
      </view>
    </view>

    <scroll-view
      class="scroll-view"
      scroll-y
      @scrolltolower="loadMore"
      refresher-enabled
      @refresherrefresh="onRefresh"
      :refresher-triggered="refreshing"
    >
      <view v-if="orderList.length > 0" class="list-box">
        <view
          v-for="order in orderList"
          :key="order.oid || order.id"
          class="item-box"
          @click="goDetail(order.oid || order.id)"
        >
          <view class="item-header">
            <view class="type-mark">
              <text>{{ getActivityTypeText(order.activityType).slice(0, 1) }}</text>
            </view>
            <view class="item-title-box">
              <text class="item-title">{{ getActivityTypeText(order.activityType) }}</text>
              <text class="item-subtitle">{{ order.location || '未设置地点' }}</text>
            </view>
            <text class="status-pill" :class="`status-${order.status || 'UNKNOWN'}`">{{ getStatusText(order.status) }}</text>
          </view>

          <view class="meta-grid">
            <view class="meta-cell">
              <text class="meta-label">时间</text>
              <text class="meta-value">{{ formatTime(order.startTime) }}</text>
            </view>
            <view class="meta-cell">
              <text class="meta-label">人数</text>
              <text class="meta-value">{{ order.currentPeople || 0 }}/{{ order.maxPeople || 0 }}</text>
            </view>
            <view class="meta-cell">
              <text class="meta-label">校区</text>
              <text class="meta-value">{{ getCampusText(order.campus) }}</text>
            </view>
          </view>

          <view class="item-actions">
            <text class="publisher" @click.stop="toProfile(order.user)">{{ order.user ? order.user.nickname : '匿名用户' }}</text>
            <button
              class="card-action"
              :class="{ danger: isPublisher(order), disabled: isActionDisabled(order) }"
              :disabled="isActionDisabled(order)"
              @click.stop="handleOrderAction(order)"
            >
              {{ getActionText(order) }}
            </button>
          </view>
        </view>
      </view>
      <view v-else-if="!loading" class="empty-box">
        <text class="empty-title">{{ onlyMine ? '暂无我发布的活动' : '暂无活动' }}</text>
        <text class="empty-text">换个筛选条件，或者发起一个新的活动。</text>
      </view>
      <view v-if="loading" class="loading-box">
        <text class="loading-text">加载中...</text>
      </view>
    </scroll-view>

    <glass-publish-menu />
  </view>
</template>

<script>
import { orderApi } from '@/api/index.js'
import { ACTIVITY_TYPE, ACTIVITY_TYPE_MAP, CAMPUS, CAMPUS_MAP, ORDER_STATUS_MAP } from '@/utils/constants.js'
import GlassPublishMenu from '@/components/glass-publish-menu/glass-publish-menu.vue'
import { goUserProfile } from '@/utils/user-navigation.js'

export default {
  components: {
    GlassPublishMenu
  },
  data() {
    return {
      orderList: [],
      appliedOrderMap: {},
      loading: false,
      refreshing: false,
      loadedOnce: false,
      page: 1,
      size: 10,
      hasMore: true,
      onlyMine: false,
      selectedType: null,
      selectedCampus: null,
      selectedStatus: null,
      typeOptions: [
        { value: null, label: '全部类型' },
        ...Object.keys(ACTIVITY_TYPE).map(key => ({
          value: ACTIVITY_TYPE[key],
          label: ACTIVITY_TYPE_MAP[ACTIVITY_TYPE[key]]
        }))
      ],
      campusOptions: [
        { value: null, label: '全部校区' },
        ...Object.keys(CAMPUS).map(key => ({
          value: CAMPUS[key],
          label: CAMPUS_MAP[CAMPUS[key]]
        }))
      ],
      statusOptions: [
        { value: null, label: '全部状态' },
        { value: 'PENDING', label: ORDER_STATUS_MAP.PENDING },
        { value: 'IN_PROGRESS', label: ORDER_STATUS_MAP.IN_PROGRESS },
        { value: 'COMPLETED', label: ORDER_STATUS_MAP.COMPLETED },
        { value: 'CANCELLED', label: ORDER_STATUS_MAP.CANCELLED },
        { value: 'EXPIRED', label: ORDER_STATUS_MAP.EXPIRED }
      ]
    }
  },
  computed: {
    currentUserId() {
      return this.$store.getters['user/userId'] || uni.getStorageSync('userId')
    },
    isLogin() {
      return this.$store.getters['user/isLogin'] || !!uni.getStorageSync('userId')
    },
    isAdmin() {
      return this.$store.getters['user/isAdmin']
    },
    hasActiveFilter() {
      return !!(this.selectedType?.value || this.selectedCampus?.value || this.selectedStatus?.value || this.onlyMine)
    },
    filterSummary() {
      const parts = []
      if (this.onlyMine) parts.push('我发布的')
      if (this.selectedType?.value) parts.push(this.selectedType.label)
      if (this.selectedCampus?.value) parts.push(this.selectedCampus.label)
      if (this.selectedStatus?.value) parts.push(this.selectedStatus.label)
      return parts.join(' · ') || '全部活动'
    }
  },
  onLoad() {
    this.applyPendingFilter()
    this.loadedOnce = true
    this.reload()
  },
  onShow() {
    if (this.loadedOnce && this.applyPendingFilter()) {
      this.reload()
    }
  },
  onPullDownRefresh() {
    this.onRefresh()
  },
  methods: {
    normalizePage(result) {
      if (Array.isArray(result)) return result
      if (Array.isArray(result?.list)) return result.list
      if (Array.isArray(result?.records)) return result.records
      return []
    },
    applyPendingFilter() {
      const legacyMode = uni.getStorageSync('orderListMode')
      const pending = uni.getStorageSync('orderListFilter') || (legacyMode ? { mode: legacyMode } : null)
      if (!pending) return false

      uni.removeStorageSync('orderListMode')
      uni.removeStorageSync('orderListFilter')

      const nextOnlyMine = pending.mode === 'mine' || pending.onlyMine === true
      const nextType = this.typeOptions.find(item => item.value === pending.activityType) || null
      const nextCampus = this.campusOptions.find(item => item.value === pending.campus) || null
      const nextStatus = this.statusOptions.find(item => item.value === pending.status) || null
      const changed =
        this.onlyMine !== nextOnlyMine ||
        (this.selectedType?.value || null) !== (nextType?.value || null) ||
        (this.selectedCampus?.value || null) !== (nextCampus?.value || null) ||
        (this.selectedStatus?.value || null) !== (nextStatus?.value || null)

      this.onlyMine = nextOnlyMine
      this.selectedType = nextType
      this.selectedCampus = nextCampus
      this.selectedStatus = nextStatus
      return changed
    },
    buildParams() {
      const params = {
        page: this.page,
        size: this.size
      }
      if (this.selectedType?.value) params.activityType = this.selectedType.value
      if (this.selectedCampus?.value) params.campus = this.selectedCampus.value
      if (this.selectedStatus?.value) params.status = this.selectedStatus.value
      return params
    },
    reload() {
      this.page = 1
      this.hasMore = true
      this.orderList = []
      this.appliedOrderMap = {}
      this.loadOrders()
    },
    async loadOrders() {
      if (this.loading) return
      if (!this.hasMore && this.page > 1) return

      if (this.onlyMine && !this.isLogin) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }

      this.loading = true
      try {
        const result = this.onlyMine
          ? await orderApi.getMyOrders(this.page, this.size)
          : await orderApi.getOrders(this.buildParams())
        const rawList = this.normalizePage(result)
        const list = this.onlyMine ? this.applyLocalFilters(rawList) : rawList
        await this.loadAppliedInfo(list)

        if (this.page === 1) {
          this.orderList = list
        } else {
          this.orderList = [...this.orderList, ...list]
        }

        this.hasMore = rawList.length >= this.size
        this.page++
      } catch (e) {
        console.error('加载活动失败:', e)
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
        this.refreshing = false
        uni.stopPullDownRefresh()
      }
    },
    applyLocalFilters(list) {
      return list.filter(order => {
        const matchType = !this.selectedType?.value || order.activityType === this.selectedType.value
        const matchCampus = !this.selectedCampus?.value || order.campus === this.selectedCampus.value
        const matchStatus = !this.selectedStatus?.value || order.status === this.selectedStatus.value
        return matchType && matchCampus && matchStatus
      })
    },
    async loadAppliedInfo(list) {
      if (!this.isLogin || !this.currentUserId || !Array.isArray(list) || !list.length) return

      const nextMap = { ...this.appliedOrderMap }
      await Promise.all(list.map(async (order) => {
        const orderId = order.id || order.oid
        if (!orderId || this.isPublisher(order)) return
        try {
          const apps = await orderApi.getApplications(orderId)
          const applied = (apps || []).some(app => {
            const appUserId = app.user && (app.user.id || app.user.uid)
            return String(appUserId || '') === String(this.currentUserId || '') && app.status !== 'CANCELLED_APPLY'
          })
          if (applied) nextMap[orderId] = true
        } catch (e) {
          console.error('加载申请状态失败:', e)
        }
      }))
      this.appliedOrderMap = nextMap
    },
    isPublisher(order) {
      if (!this.isLogin || !order?.user) return false
      if (this.isAdmin) return true
      const publisherId = order.user.id || order.user.uid
      return String(publisherId || '') === String(this.currentUserId || '')
    },
    hasApplied(order) {
      const orderId = order.id || order.oid
      return !!this.appliedOrderMap[orderId]
    },
    isActionDisabled(order) {
      if (!order) return true
      if (this.isPublisher(order)) {
        return order.status !== 'PENDING'
      }
      if (!this.isLogin) return false
      if (this.hasApplied(order)) return true
      if (order.status !== 'PENDING') return true
      if ((order.currentPeople || 0) >= (order.maxPeople || 0)) return true
      return false
    },
    getActionText(order) {
      if (!this.isLogin) return '登录后申请'
      if (this.isPublisher(order)) {
        if (order.status === 'PENDING') return '取消活动'
        return '不可操作'
      }
      if (this.hasApplied(order)) return '已申请'
      if (order.status === 'EXPIRED') return '已过期'
      if (order.status === 'IN_PROGRESS') return '进行中'
      if (order.status === 'COMPLETED') return '已完成'
      if (order.status === 'CANCELLED') return '已取消'
      if ((order.currentPeople || 0) >= (order.maxPeople || 0)) return '人数已满'
      return '申请加入'
    },
    handleOrderAction(order) {
      const orderId = order.id || order.oid
      if (!orderId) return

      if (!this.isLogin) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }

      if (this.isPublisher(order)) {
        this.cancelOrder(orderId)
        return
      }

      if (this.isActionDisabled(order)) return
      this.applyOrder(orderId)
    },
    applyOrder(orderId) {
      uni.showModal({
        title: '申请加入',
        content: '确定申请加入这个活动吗？',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await orderApi.applyOrder(orderId)
            this.appliedOrderMap = { ...this.appliedOrderMap, [orderId]: true }
            uni.showToast({ title: '申请成功', icon: 'success' })
            this.reload()
          } catch (error) {
            uni.showToast({ title: error.message || '申请失败', icon: 'none' })
          }
        }
      })
    },
    cancelOrder(orderId) {
      uni.showModal({
        title: '取消活动',
        content: '确定取消这个活动吗？此操作不可撤销。',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await orderApi.deleteOrder(orderId)
            uni.showToast({ title: '已取消', icon: 'success' })
            this.reload()
          } catch (error) {
            uni.showToast({ title: error.message || '取消失败', icon: 'none' })
          }
        }
      })
    },
    clearMode() {
      this.onlyMine = false
      this.selectedType = null
      this.selectedCampus = null
      this.selectedStatus = null
      this.reload()
    },
    toggleOnlyMine() {
      this.onlyMine = !this.onlyMine
      this.reload()
    },
    onRefresh() {
      this.page = 1
      this.hasMore = true
      this.refreshing = true
      this.loadOrders()
    },
    loadMore() {
      this.loadOrders()
    },
    onTypeChange(e) {
      this.selectedType = this.typeOptions[e.detail.value]
      this.reload()
    },
    onCampusChange(e) {
      this.selectedCampus = this.campusOptions[e.detail.value]
      this.reload()
    },
    onStatusChange(e) {
      this.selectedStatus = this.statusOptions[e.detail.value]
      this.reload()
    },
    goDetail(id) {
      uni.navigateTo({ url: `/pages/order/detail?id=${id}` })
    },
    goCreate() {
      if (!this.isLogin) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }
      uni.navigateTo({ url: '/pages/order/create' })
    },
    toProfile(user) {
      goUserProfile(user)
    },
    getActivityTypeText(type) {
      return ACTIVITY_TYPE_MAP[type] || '其他'
    },
    getCampusText(campus) {
      return CAMPUS_MAP[campus] || '其他校区'
    },
    getStatusText(status) {
      return ORDER_STATUS_MAP[status] || '未知'
    },
    formatTime(timeStr) {
      if (!timeStr) return '未设置'
      try {
        const date = new Date(timeStr)
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        return `${month}-${day} ${hours}:${minutes}`
      } catch (e) {
        return timeStr
      }
    }
  }
}
</script>

<style>
.page {
  width: 100%;
  height: 100vh;
  background:
    radial-gradient(circle at 18% 2%, rgba(78, 161, 255, 0.16), transparent 32%),
    radial-gradient(circle at 92% 0%, rgba(30, 194, 214, 0.10), transparent 28%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #f9fbff 100%);
  display: flex;
  flex-direction: column;
}

.app-top {
  padding: 44rpx 30rpx 58rpx;
  background: #1f447a;
  color: #ffffff;
  flex-shrink: 0;
}

.title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
}

.title-row view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.page-title {
  font-size: 42rpx;
  font-weight: 800;
  line-height: 1.15;
}

.page-subtitle {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.78);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-action {
  width: 112rpx;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  border: 1rpx solid rgba(255, 255, 255, 0.32);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  font-size: 24rpx;
}

.filter-card {
  margin: -38rpx 30rpx 12rpx;
  padding: 20rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(238, 248, 255, 0.72));
  border: 1rpx solid rgba(255, 255, 255, 0.76);
  border-radius: 30rpx;
  box-shadow:
    0 18rpx 38rpx rgba(23, 42, 79, 0.13),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  flex-shrink: 0;
  -webkit-backdrop-filter: blur(24rpx) saturate(1.26);
  backdrop-filter: blur(24rpx) saturate(1.26);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
}

.filter-item {
  min-height: 64rpx;
  padding: 0 14rpx;
  background: rgba(255, 255, 255, 0.64);
  border: 1rpx solid rgba(222, 235, 248, 0.9);
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8rpx;
  color: #344054;
  font-size: 23rpx;
}

.filter-item text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  width: 12rpx;
  height: 12rpx;
  border-right: 3rpx solid #8a94a6;
  border-bottom: 3rpx solid #8a94a6;
  transform: rotate(45deg);
  flex: 0 0 12rpx;
}

.filter-bottom {
  margin-top: 14rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filter-toggle {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  color: #667085;
  font-size: 24rpx;
}

.filter-toggle.active {
  color: #1f447a;
  font-weight: 700;
}

.toggle-dot {
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  border: 4rpx solid currentColor;
  box-sizing: border-box;
}

.mode-clear {
  color: #1f447a;
  font-size: 24rpx;
  font-weight: 700;
}

.scroll-view {
  width: 100%;
  flex: 1;
  height: 0;
}

.list-box {
  padding: 16rpx 30rpx 170rpx;
}

.item-box {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.76));
  padding: 26rpx;
  border-radius: 30rpx;
  margin-bottom: 18rpx;
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  border: 1rpx solid rgba(255, 255, 255, 0.76);
}

.item-box::before {
  content: "";
  position: absolute;
  left: 0;
  top: 26rpx;
  bottom: 26rpx;
  width: 7rpx;
  border-radius: 0 999rpx 999rpx 0;
  background: linear-gradient(180deg, #2f7ed8, #1ec2d6);
}

.item-header {
  display: flex;
  align-items: center;
  margin-bottom: 22rpx;
}

.type-mark {
  width: 62rpx;
  height: 62rpx;
  border-radius: 20rpx;
  background:
    radial-gradient(circle at 28% 20%, rgba(255, 255, 255, 0.92), transparent 42%),
    linear-gradient(145deg, rgba(237, 247, 255, 0.96), rgba(210, 231, 255, 0.78));
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  margin-right: 16rpx;
  flex-shrink: 0;
}

.item-title-box {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.item-title {
  font-size: 31rpx;
  font-weight: 800;
  color: #172033;
}

.item-subtitle {
  font-size: 23rpx;
  color: #8a94a6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  padding: 7rpx 16rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  color: #1f447a;
  background: #edf4ff;
  flex-shrink: 0;
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

.meta-grid {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr 1fr;
  gap: 12rpx;
  padding: 18rpx;
  background: rgba(255, 255, 255, 0.58);
  border: 1rpx solid rgba(229, 237, 247, 0.86);
  border-radius: 22rpx;
}

.meta-cell {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.meta-label {
  font-size: 21rpx;
  color: #8a94a6;
}

.meta-value {
  font-size: 25rpx;
  color: #344054;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 22rpx;
}

.publisher {
  color: #667085;
  font-size: 24rpx;
}

.card-action {
  min-width: 156rpx;
  height: 62rpx;
  padding: 0 22rpx;
  border: none;
  border-radius: 999rpx;
  background:
    linear-gradient(135deg, rgba(47, 126, 216, 0.96), rgba(31, 68, 122, 0.96));
  color: #ffffff;
  font-size: 24rpx;
  line-height: 62rpx;
  box-shadow: 0 12rpx 24rpx rgba(31, 68, 122, 0.18);
}

.card-action.danger {
  background: #fff1f0;
  color: #b42318;
}

.card-action.disabled {
  background: #eef1f5;
  color: #8a94a6;
}

.empty-box,
.loading-box {
  text-align: center;
  padding: 100rpx 40rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.loading-box {
  padding: 50rpx 0;
}

.empty-title {
  font-size: 30rpx;
  color: #172033;
  font-weight: 800;
}

.empty-text,
.loading-text {
  font-size: 26rpx;
  color: #8a94a6;
}

</style>
