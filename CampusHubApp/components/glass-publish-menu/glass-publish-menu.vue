<template>
  <view class="publish-menu" :class="{ open: isOpen }">
    <view v-if="isOpen" class="publish-backdrop" @click="close"></view>

    <view class="publish-actions" :class="{ visible: isOpen }">
      <view class="publish-option" @click="goCreateOrder">
        <view class="option-icon order-icon">
          <view class="order-line"></view>
          <view class="order-dots">
            <view></view>
            <view></view>
            <view></view>
          </view>
        </view>
        <view class="option-copy">
          <text class="option-title">发起订单</text>
          <text class="option-desc">约同学一起活动</text>
        </view>
      </view>

      <view class="publish-option" @click="goCreateContent">
        <view class="option-icon content-icon">
          <view class="content-line wide"></view>
          <view class="content-line"></view>
          <view class="content-tail"></view>
        </view>
        <view class="option-copy">
          <text class="option-title">发布动态</text>
          <text class="option-desc">记录校园片段</text>
        </view>
      </view>
    </view>

    <view class="glass-fab" :class="{ active: isOpen }" @click.stop="toggle">
      <view class="fab-plus">
        <view class="fab-h"></view>
        <view class="fab-v"></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

const isOpen = ref(false)

const isLogin = () => Boolean(uni.getStorageSync('userId') || uni.getStorageSync('token'))

const toggle = () => {
  isOpen.value = !isOpen.value
}

const close = () => {
  isOpen.value = false
}

const navigateToCreate = (url) => {
  close()
  if (!isLogin()) {
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }
  uni.navigateTo({ url })
}

const goCreateOrder = () => {
  navigateToCreate('/pages/order/create')
}

const goCreateContent = () => {
  navigateToCreate('/pages/content/create')
}
</script>

<style scoped>
.publish-menu {
  position: fixed;
  right: 30rpx;
  bottom: 176rpx;
  z-index: 999;
}

.publish-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(12, 23, 42, 0.04);
  z-index: 1;
}

.publish-actions {
  position: absolute;
  right: 0;
  bottom: 112rpx;
  width: 330rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  pointer-events: none;
  opacity: 0;
  transform: translateY(22rpx) scale(0.96);
  transition: opacity 0.22s ease, transform 0.22s ease;
  z-index: 2;
}

.publish-actions.visible {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}

.publish-option {
  position: relative;
  min-height: 104rpx;
  padding: 18rpx;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.62);
  background:
    radial-gradient(circle at 20% 8%, rgba(255, 255, 255, 0.64), transparent 38%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.36), rgba(255, 255, 255, 0.18));
  box-shadow:
    0 22rpx 44rpx rgba(23, 50, 86, 0.14),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.86),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.46),
    inset 0 -16rpx 30rpx rgba(219, 238, 255, 0.10);
  -webkit-backdrop-filter: blur(22rpx) saturate(1.78) contrast(1.04);
  backdrop-filter: blur(22rpx) saturate(1.78) contrast(1.04);
  display: flex;
  align-items: center;
  gap: 16rpx;
  overflow: hidden;
}

.publish-option::before {
  content: "";
  position: absolute;
  left: 18rpx;
  right: 18rpx;
  top: 8rpx;
  height: 26rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.64), rgba(255, 255, 255, 0.06));
  pointer-events: none;
}

.publish-option:active {
  transform: scale(0.975);
  opacity: 0.9;
}

.option-icon {
  position: relative;
  width: 70rpx;
  height: 70rpx;
  flex: 0 0 70rpx;
  border-radius: 22rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(215, 235, 255, 0.72));
  box-shadow:
    0 12rpx 26rpx rgba(31, 68, 122, 0.14),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.96);
  color: #1f447a;
}

.order-line {
  position: absolute;
  left: 19rpx;
  top: 17rpx;
  width: 32rpx;
  height: 28rpx;
  border: 4rpx solid currentColor;
  border-top-width: 10rpx;
  border-radius: 10rpx;
  box-sizing: border-box;
}

.order-dots {
  position: absolute;
  left: 24rpx;
  top: 39rpx;
  display: flex;
  gap: 5rpx;
}

.order-dots view {
  width: 6rpx;
  height: 6rpx;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.68;
}

.content-icon::before {
  content: "";
  position: absolute;
  left: 17rpx;
  top: 18rpx;
  width: 38rpx;
  height: 28rpx;
  border: 4rpx solid currentColor;
  border-radius: 14rpx;
  box-sizing: border-box;
}

.content-line {
  position: absolute;
  left: 26rpx;
  top: 29rpx;
  width: 18rpx;
  height: 5rpx;
  border-radius: 999rpx;
  background: currentColor;
}

.content-line.wide {
  top: 22rpx;
  width: 22rpx;
}

.content-tail {
  position: absolute;
  left: 24rpx;
  top: 44rpx;
  width: 13rpx;
  height: 13rpx;
  border-left: 4rpx solid currentColor;
  border-bottom: 4rpx solid currentColor;
  transform: skew(-18deg);
  border-radius: 0 0 0 5rpx;
}

.option-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.option-title {
  color: #13233d;
  font-size: 28rpx;
  font-weight: 800;
}

.option-desc {
  color: #667085;
  font-size: 22rpx;
}

.glass-fab {
  position: relative;
  z-index: 3;
  width: 96rpx;
  height: 96rpx;
  border-radius: 36rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.64);
  background:
    radial-gradient(circle at 24% 12%, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.18) 32%, transparent 55%),
    radial-gradient(circle at 76% 86%, rgba(255, 255, 255, 0.30), transparent 38%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.14));
  box-shadow:
    0 24rpx 48rpx rgba(31, 68, 122, 0.18),
    0 4rpx 10rpx rgba(255, 255, 255, 0.18),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.88),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.46),
    inset 0 -18rpx 34rpx rgba(214, 234, 255, 0.12);
  -webkit-backdrop-filter: blur(22rpx) saturate(1.85) contrast(1.04);
  backdrop-filter: blur(22rpx) saturate(1.85) contrast(1.04);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.22s ease, border-radius 0.22s ease, box-shadow 0.22s ease;
  overflow: hidden;
}

.glass-fab::before {
  content: "";
  position: absolute;
  inset: 1rpx;
  border-radius: inherit;
  box-shadow:
    inset 14rpx 0 30rpx rgba(255, 255, 255, 0.16),
    inset -10rpx -8rpx 24rpx rgba(255, 255, 255, 0.10);
  pointer-events: none;
}

.glass-fab::after {
  content: "";
  position: absolute;
  left: 14rpx;
  right: 14rpx;
  top: 9rpx;
  height: 22rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.66), rgba(255, 255, 255, 0.04));
}

.glass-fab.active {
  transform: rotate(45deg) scale(0.98);
  border-radius: 38rpx;
}

.fab-plus {
  position: relative;
  z-index: 1;
  width: 42rpx;
  height: 42rpx;
}

.fab-h,
.fab-v {
  position: absolute;
  left: 50%;
  top: 50%;
  border-radius: 999rpx;
  background: #173b68;
  box-shadow:
    0 1rpx 1rpx rgba(255, 255, 255, 0.70),
    0 8rpx 16rpx rgba(11, 31, 63, 0.12);
  transform: translate(-50%, -50%);
}

.fab-h {
  width: 40rpx;
  height: 7rpx;
}

.fab-v {
  width: 7rpx;
  height: 40rpx;
}
</style>
