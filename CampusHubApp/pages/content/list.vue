<template>
  <view class="page">
    <view class="app-top">
      <view class="title-row">
        <view>
          <text class="page-title">动态</text>
          <text class="page-subtitle">{{ modeText }}</text>
        </view>
      </view>
    </view>

    <view v-if="listMode === 'mine' || searchKeyword" class="mode-card">
      <text>{{ modeText }}</text>
      <text class="mode-clear" @click="clearMode">查看全部</text>
    </view>

    <scroll-view
      class="scroll-view"
      scroll-y
      @scrolltolower="loadMore"
      refresher-enabled
      @refresherrefresh="onRefresh"
      :refresher-triggered="refreshing"
    >
      <view v-if="contentList.length > 0" class="list-box">
        <view
          v-for="content in contentList"
          :key="content.pid || content.id"
          class="item-box"
          @click="goDetail(content.pid || content.id)"
        >
          <view class="item-main">
            <view class="item-header">
              <image
                v-if="content.user && content.user.avatarUrl"
                :src="content.user.avatarUrl"
                class="avatar"
                mode="aspectFill"
                @click.stop="toProfile(content.user)"
              />
              <view v-else class="avatar-placeholder" @click.stop="toProfile(content.user)">
                <text>{{ getUserInitial(content.user) }}</text>
              </view>
              <view class="user-meta">
                <text class="user-name" @click.stop="toProfile(content.user)">{{ content.user ? content.user.nickname : '匿名用户' }}</text>
                <text class="item-time">{{ formatRelativeTime(content.createdAt) }}</text>
              </view>
            </view>
            <text class="item-text">{{ content.content || '暂无内容' }}</text>
            <view class="item-footer">
              <view class="action-chip">
                <view class="chip-icon like-icon"></view>
                <text>{{ content.likeCount || 0 }}</text>
              </view>
              <view class="action-chip">
                <view class="chip-icon comment-icon"></view>
                <text>{{ content.commentCount || 0 }}</text>
              </view>
            </view>
          </view>
          <image
            v-if="content.media && content.media.length"
            :src="content.media[0].url"
            class="item-thumb"
            mode="aspectFill"
          />
        </view>
      </view>
      <view v-else-if="!loading" class="empty-box">
        <text class="empty-title">{{ emptyText }}</text>
        <text class="empty-text">可以发一条动态，记录今天的校园片段。</text>
      </view>
      <view v-if="loading" class="loading-box">
        <text class="loading-text">加载中...</text>
      </view>
    </scroll-view>

    <glass-publish-menu />
  </view>
</template>

<script>
import { contentApi } from '@/api/index.js'
import { normalizeMediaList, formatRelativeTime, resolveFileUrl } from '@/utils/util.js'
import GlassPublishMenu from '@/components/glass-publish-menu/glass-publish-menu.vue'
import { goUserProfile } from '@/utils/user-navigation.js'

export default {
  components: {
    GlassPublishMenu
  },
  data() {
    return {
      contentList: [],
      loading: false,
      refreshing: false,
      loadedOnce: false,
      page: 1,
      size: 10,
      hasMore: true,
      listMode: 'all',
      searchKeyword: ''
    }
  },
  computed: {
    modeText() {
      if (this.listMode === 'mine' && this.searchKeyword) return `我的动态 · ${this.searchKeyword}`
      if (this.listMode === 'mine') return '我的动态'
      if (this.searchKeyword) return `搜索：${this.searchKeyword}`
      return '校园里的即时分享'
    },
    emptyText() {
      if (this.listMode === 'mine' && this.searchKeyword) return '暂无匹配的我的动态'
      if (this.listMode === 'mine') return '暂无我的动态'
      if (this.searchKeyword) return '暂无匹配动态'
      return '暂无动态'
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
      const pending = uni.getStorageSync('contentListFilter')
      if (!pending) return false

      uni.removeStorageSync('contentListFilter')
      const nextMode = pending.mode === 'mine' ? 'mine' : 'all'
      const nextKeyword = pending.keyword || ''
      const changed = this.listMode !== nextMode || this.searchKeyword !== nextKeyword

      this.listMode = nextMode
      this.searchKeyword = nextKeyword
      return changed
    },
    reload() {
      this.page = 1
      this.hasMore = true
      this.contentList = []
      this.loadContents()
    },
    async loadContents() {
      if (this.loading || !this.hasMore) return

      if (this.listMode === 'mine' && !uni.getStorageSync('userId')) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }

      this.loading = true
      try {
        const result = this.searchKeyword
          ? await contentApi.searchByKeyword(this.searchKeyword, this.page, this.size)
          : await contentApi.getContents({ page: this.page, size: this.size })

        const rawList = this.normalizePage(result).map(item => ({
          ...item,
          user: item.user ? {
            ...item.user,
            avatarUrl: resolveFileUrl(item.user.avatarUrl)
          } : item.user,
          media: normalizeMediaList(item)
        }))
        const list = this.listMode === 'mine' ? this.filterMine(rawList) : rawList

        if (this.page === 1) {
          this.contentList = list
        } else {
          this.contentList = [...this.contentList, ...list]
        }

        this.hasMore = rawList.length >= this.size
        this.page++
      } catch (e) {
        console.error('加载动态失败:', e)
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
        this.refreshing = false
        uni.stopPullDownRefresh()
      }
    },
    filterMine(list) {
      const userId = String(uni.getStorageSync('userId') || '')
      return list.filter(item => {
        const ownerId = item.user && (item.user.id || item.user.uid)
        return String(ownerId || '') === userId
      })
    },
    clearMode() {
      this.listMode = 'all'
      this.searchKeyword = ''
      this.reload()
    },
    onRefresh() {
      this.page = 1
      this.hasMore = true
      this.refreshing = true
      this.loadContents()
    },
    loadMore() {
      this.loadContents()
    },
    getUserInitial(user) {
      return user && user.nickname ? user.nickname.slice(0, 1) : '用'
    },
    formatRelativeTime,
    goDetail(id) {
      uni.navigateTo({ url: `/pages/content/detail?id=${id}` })
    },
    goCreate() {
      if (!uni.getStorageSync('userId')) {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }
      uni.navigateTo({ url: '/pages/content/create' })
    },
    toProfile(user) {
      goUserProfile(user)
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

.mode-card {
  margin: -38rpx 30rpx 12rpx;
  padding: 20rpx 24rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(238, 248, 255, 0.72));
  border: 1rpx solid rgba(255, 255, 255, 0.76);
  border-radius: 30rpx;
  box-shadow:
    0 18rpx 38rpx rgba(23, 42, 79, 0.13),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #1f447a;
  font-size: 25rpx;
  font-weight: 700;
  flex-shrink: 0;
}

.mode-clear {
  color: #667085;
  font-weight: 500;
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
  display: flex;
  gap: 18rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.76));
  padding: 24rpx;
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
  left: 22rpx;
  right: 22rpx;
  top: 10rpx;
  height: 24rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.08));
  pointer-events: none;
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-header {
  display: flex;
  align-items: center;
  margin-bottom: 16rpx;
}

.avatar,
.avatar-placeholder {
  width: 58rpx;
  height: 58rpx;
  border-radius: 50%;
  margin-right: 14rpx;
  flex-shrink: 0;
}

.avatar-placeholder {
  background:
    radial-gradient(circle at 32% 22%, rgba(255, 255, 255, 0.88), transparent 42%),
    linear-gradient(145deg, rgba(237, 247, 255, 0.96), rgba(210, 231, 255, 0.78));
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 800;
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 28rpx;
  font-weight: 800;
  color: #172033;
}

.item-time {
  font-size: 22rpx;
  color: #8a94a6;
  margin-top: 4rpx;
}

.item-text {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 28rpx;
  color: #344054;
  line-height: 1.6;
}

.item-thumb {
  width: 148rpx;
  height: 148rpx;
  border-radius: 24rpx;
  background: #eef1f5;
  flex-shrink: 0;
  box-shadow: 0 12rpx 26rpx rgba(22, 47, 84, 0.10);
}

.item-footer {
  display: flex;
  gap: 22rpx;
  margin-top: 18rpx;
}

.action-chip {
  display: flex;
  align-items: center;
  gap: 8rpx;
  color: #667085;
  font-size: 24rpx;
  padding: 8rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(229, 237, 247, 0.86);
}

.chip-icon {
  width: 24rpx;
  height: 24rpx;
  position: relative;
}

.like-icon::before {
  content: '';
  position: absolute;
  left: 4rpx;
  top: 4rpx;
  width: 14rpx;
  height: 14rpx;
  border: 4rpx solid #8a94a6;
  border-top: none;
  border-left: none;
  transform: rotate(-45deg);
  border-radius: 3rpx;
}

.comment-icon {
  border: 4rpx solid #8a94a6;
  border-radius: 8rpx;
  box-sizing: border-box;
}

.comment-icon::after {
  content: '';
  position: absolute;
  left: 3rpx;
  bottom: -6rpx;
  width: 8rpx;
  height: 8rpx;
  border-left: 4rpx solid #8a94a6;
  border-bottom: 4rpx solid #8a94a6;
  transform: rotate(-25deg);
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
