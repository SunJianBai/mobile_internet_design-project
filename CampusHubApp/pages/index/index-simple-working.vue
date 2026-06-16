<template>
  <view class="home-container">
    <view class="home-header">
      <text class="app-title">CampusHub</text>
      <view class="header-right" @click="toUserProfile">
        <view class="avatar-placeholder">
          <text class="avatar-text">我</text>
        </view>
      </view>
    </view>

    <view class="search-bar">
      <view class="search-icon"></view>
      <text class="search-placeholder">搜索活动、动态或用户</text>
    </view>

    <view class="function-grid">
      <view class="function-item" @click="toOrderList">
        <view class="function-icon target-icon"></view>
        <text class="function-text">活动广场</text>
      </view>
      <view class="function-item" @click="toContentList">
        <view class="function-icon note-icon"></view>
        <text class="function-text">动态社区</text>
      </view>
      <view class="function-item" @click="toCreateOrder">
        <view class="function-icon plus-icon"></view>
        <text class="function-text">发布活动</text>
      </view>
      <view class="function-item" @click="toAIChat">
        <view class="function-icon ai-icon"></view>
        <text class="function-text">AI助手</text>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">推荐活动</text>
        <text class="section-more" @click="toOrderList">更多 ></text>
      </view>
      <view class="empty-state">
        <text class="empty-text">暂无推荐活动</text>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">热门动态</text>
        <text class="section-more" @click="toContentList">更多 ></text>
      </view>
      <view class="empty-state">
        <text class="empty-text">暂无热门动态</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  methods: {
    toOrderList() {
      uni.switchTab({ url: '/pages/order/list' })
    },
    toContentList() {
      uni.switchTab({ url: '/pages/content/list' })
    },
    toCreateOrder() {
      uni.navigateTo({ url: '/pages/order/create' })
    },
    toUserProfile() {
      uni.switchTab({ url: '/pages/user/info' })
    },
    toAIChat() {
      uni.navigateTo({ url: '/pages/ai/chat' })
    }
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: #f5f7fb;
  padding-bottom: 40rpx;
}

.home-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 40rpx 30rpx 20rpx;
  background: #ffffff;
}

.app-title {
  color: #172033;
  font-size: 48rpx;
  font-weight: 800;
}

.header-right,
.avatar-placeholder {
  width: 80rpx;
  height: 80rpx;
}

.avatar-placeholder {
  border-radius: 50%;
  background: #1d4ed8;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-text {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 700;
}

.search-bar {
  margin: 20rpx 30rpx;
  padding: 24rpx 30rpx;
  display: flex;
  align-items: center;
  gap: 14rpx;
  background: #ffffff;
  border-radius: 8rpx;
}

.search-icon {
  position: relative;
  width: 30rpx;
  height: 30rpx;
  border: 3rpx solid #98a2b3;
  border-radius: 50%;
  box-sizing: border-box;
}

.search-icon::after {
  content: "";
  position: absolute;
  width: 13rpx;
  height: 3rpx;
  right: -9rpx;
  bottom: -5rpx;
  border-radius: 999rpx;
  background: #98a2b3;
  transform: rotate(45deg);
}

.search-placeholder {
  color: #8a94a6;
  font-size: 28rpx;
}

.function-grid {
  display: flex;
  justify-content: space-around;
  padding: 40rpx 30rpx;
  background: #ffffff;
  margin: 20rpx 30rpx;
  border-radius: 8rpx;
}

.function-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
}

.function-icon {
  position: relative;
  width: 58rpx;
  height: 58rpx;
}

.target-icon {
  border: 4rpx solid #1d4ed8;
  border-radius: 50%;
  box-sizing: border-box;
}

.target-icon::before {
  content: "";
  position: absolute;
  inset: 13rpx;
  border: 4rpx solid #1d4ed8;
  border-radius: 50%;
}

.note-icon,
.ai-icon {
  border: 4rpx solid #1d4ed8;
  border-radius: 8rpx;
  box-sizing: border-box;
}

.note-icon::before,
.note-icon::after {
  content: "";
  position: absolute;
  left: 13rpx;
  width: 28rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: #1d4ed8;
}

.note-icon::before {
  top: 17rpx;
}

.note-icon::after {
  top: 34rpx;
}

.plus-icon::before,
.plus-icon::after {
  content: "";
  position: absolute;
  left: 8rpx;
  top: 26rpx;
  width: 42rpx;
  height: 6rpx;
  border-radius: 999rpx;
  background: #1d4ed8;
}

.plus-icon::after {
  transform: rotate(90deg);
}

.ai-icon::before {
  content: "";
  position: absolute;
  left: 15rpx;
  top: 15rpx;
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: #1d4ed8;
  box-shadow: 16rpx 0 0 #1d4ed8;
}

.ai-icon::after {
  content: "";
  position: absolute;
  left: 18rpx;
  bottom: 12rpx;
  width: 20rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: #1d4ed8;
}

.function-text {
  color: #667085;
  font-size: 24rpx;
}

.section {
  margin: 20rpx 30rpx;
  background: #ffffff;
  border-radius: 8rpx;
  padding: 30rpx;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
}

.section-title {
  color: #172033;
  font-size: 36rpx;
  font-weight: 800;
}

.section-more {
  color: #1d4ed8;
  font-size: 26rpx;
}

.empty-state {
  text-align: center;
  padding: 60rpx 0;
}

.empty-text {
  color: #98a2b3;
  font-size: 28rpx;
}
</style>
