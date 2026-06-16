<script>
import config from './utils/config.js'
import store from './store/index.js'

export default {
  onLaunch() {
    console.log('App launch', config.baseURL)
    store.dispatch('user/initUserState').catch((error) => {
      console.error('Init user state failed:', error)
    })
  },
  onShow() {
    console.log('App show')
  },
  onHide() {
    console.log('App hide')
  }
}
</script>

<style>
page {
  background:
    radial-gradient(circle at 18% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 46%, #f8fbff 100%);
  height: 100%;
  color: #172033;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

uni-page-body {
  min-height: 100%;
}

.container,
.page,
.user-info-container,
.chat-container,
.content-page,
.detail-page,
.create-page {
  background:
    radial-gradient(circle at 16% 2%, rgba(78, 161, 255, 0.18), transparent 32%),
    radial-gradient(circle at 88% 8%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 48%, #f8fbff 100%) !important;
}

.uni-app--showtabbar .container,
.uni-app--showtabbar .user-info-container {
  padding-bottom: 156rpx !important;
  box-sizing: border-box;
}

.uni-app--showtabbar .list-box,
.uni-app--showtabbar .empty-box,
.uni-app--showtabbar .loading-box {
  padding-bottom: 146rpx;
  box-sizing: border-box;
}

.app-top {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(23, 55, 105, 0.98) 0%, rgba(31, 68, 122, 0.98) 48%, rgba(35, 108, 151, 0.96) 100%) !important;
  box-shadow: inset 0 -1rpx 0 rgba(255, 255, 255, 0.18);
}

.app-top::before {
  content: "";
  position: absolute;
  left: -18%;
  top: -42%;
  width: 72%;
  height: 120%;
  background: linear-gradient(118deg, rgba(255, 255, 255, 0.26), rgba(255, 255, 255, 0.04) 58%, transparent);
  transform: rotate(-11deg);
  pointer-events: none;
  animation: header-sheen 8s ease-in-out infinite alternate;
}

.app-top::after {
  content: "";
  position: absolute;
  right: 26rpx;
  bottom: -72rpx;
  width: 220rpx;
  height: 220rpx;
  border-radius: 999rpx;
  background: radial-gradient(circle, rgba(125, 222, 255, 0.22), transparent 70%);
  pointer-events: none;
}

.app-top > * {
  position: relative;
  z-index: 1;
}

.profile-card,
.login-card,
.shortcut-card,
.menu-list,
.menu-grid,
.metric-card,
.search-box,
.section,
.filter-card,
.mode-card,
.item-box,
.order-item,
.content-item,
.form-card,
.detail-card,
.content-card,
.comment-card,
.reply-card,
.apply-card,
.message-bubble,
.assistant-bubble,
.empty-state,
.empty-box,
.memory-panel {
  border: 1rpx solid rgba(255, 255, 255, 0.72) !important;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(246, 251, 255, 0.72)) !important;
  box-shadow:
    0 20rpx 42rpx rgba(22, 47, 84, 0.11),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.82) !important;
  -webkit-backdrop-filter: blur(22rpx) saturate(1.28);
  backdrop-filter: blur(22rpx) saturate(1.28);
}

.app-top .metric-card {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.10)) !important;
  border-color: rgba(255, 255, 255, 0.32) !important;
  box-shadow:
    0 14rpx 30rpx rgba(8, 29, 61, 0.12),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.46) !important;
}

.app-top .metric-num,
.app-top .metric-label {
  color: #ffffff !important;
  text-shadow: 0 1rpx 8rpx rgba(11, 29, 54, 0.18);
}

.app-top .metric-label {
  opacity: 0.84;
}

.search-box,
.filter-card,
.profile-card,
.login-card,
.section,
.item-box,
.menu-grid,
.menu-list,
.content-card,
.detail-card,
.form-card,
.empty-state,
.empty-box {
  border-radius: 28rpx !important;
}

.shortcut-card,
.metric-card,
.order-item,
.content-item,
.comment-card,
.reply-card,
.apply-card,
.assistant-bubble,
.message-bubble {
  border-radius: 24rpx !important;
}

.top-action,
.send-btn,
.submit-btn,
.login-btn,
.logout-btn,
.bottom-btn,
.tool-btn,
.memory-close,
.mode-clear,
.status-pill,
.action-btn,
.publish-btn {
  transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
}

.top-action:active,
.send-btn:active,
.submit-btn:active,
.login-btn:active,
.logout-btn:active,
.bottom-btn:active,
.tool-btn:active,
.memory-close:active,
.mode-clear:active,
.action-btn:active,
.publish-btn:active,
.menu-item:active,
.item-box:active,
.order-item:active,
.content-item:active,
.shortcut-card:active,
.search-box:active {
  transform: scale(0.975);
  opacity: 0.88;
}

.profile-card,
.login-card,
.search-box,
.menu-grid,
.filter-card,
.mode-card,
.section,
.shortcut-card,
.item-box,
.order-item,
.content-item,
.assistant-row,
.user-bubble {
  animation: glass-rise 0.48s cubic-bezier(0.2, 0.78, 0.25, 1) both;
}

.section:nth-of-type(2),
.item-box:nth-child(2),
.shortcut-card:nth-child(2),
.content-item:nth-child(2),
.order-item:nth-child(2) {
  animation-delay: 0.05s;
}

.section:nth-of-type(3),
.item-box:nth-child(3),
.content-item:nth-child(3),
.order-item:nth-child(3) {
  animation-delay: 0.1s;
}

.avatar-box,
.avatar-wrap,
.type-mark,
.assistant-avatar,
.empty-logo,
.menu-icon,
.camera-badge {
  box-shadow:
    inset 0 1rpx 0 rgba(255, 255, 255, 0.75),
    0 12rpx 28rpx rgba(23, 42, 79, 0.14);
}

.avatar-box,
.avatar-wrap {
  animation: soft-float 4.8s ease-in-out infinite;
}

.profile-card .avatar,
.profile-card .avatar-placeholder,
.login-card .login-illustration {
  border-color: rgba(236, 246, 255, 0.92) !important;
  box-shadow:
    0 0 0 10rpx rgba(255, 255, 255, 0.58),
    0 16rpx 34rpx rgba(23, 42, 79, 0.16);
}

.menu-grid .menu-icon {
  background-color: rgba(232, 243, 255, 0.78) !important;
  box-shadow:
    0 0 0 8rpx rgba(31, 68, 122, 0.055),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.88);
}

.top-action,
.send-btn,
.submit-btn,
.login-btn,
.bottom-btn.primary,
.tool-btn.subtle {
  background:
    linear-gradient(135deg, rgba(40, 90, 158, 0.96), rgba(31, 68, 122, 0.96)) !important;
  box-shadow: 0 14rpx 30rpx rgba(31, 68, 122, 0.22);
}

.input-bar,
.bottom-actions {
  border-top: 1rpx solid rgba(255, 255, 255, 0.74) !important;
  background: rgba(248, 251, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(24rpx) saturate(1.25);
  backdrop-filter: blur(24rpx) saturate(1.25);
}

uni-tabbar .uni-tabbar {
  left: 10rpx !important;
  right: 10rpx !important;
  bottom: 14rpx !important;
  width: auto !important;
  height: 128rpx !important;
  padding: 12rpx 12rpx calc(12rpx + env(safe-area-inset-bottom)) !important;
  border: 1rpx solid rgba(255, 255, 255, 0.64) !important;
  border-radius: 40rpx !important;
  background:
    radial-gradient(circle at 18% 8%, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.16) 28%, transparent 52%),
    radial-gradient(circle at 82% 88%, rgba(255, 255, 255, 0.36), transparent 38%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.30), rgba(255, 255, 255, 0.14)) !important;
  box-shadow:
    0 24rpx 52rpx rgba(22, 47, 84, 0.16),
    0 4rpx 10rpx rgba(255, 255, 255, 0.18),
    inset 1rpx 1rpx 2rpx rgba(255, 255, 255, 0.84),
    inset -1rpx -1rpx 2rpx rgba(255, 255, 255, 0.58),
    inset 0 -18rpx 36rpx rgba(216, 236, 255, 0.12) !important;
  -webkit-backdrop-filter: blur(22rpx) saturate(1.85) contrast(1.04);
  backdrop-filter: blur(22rpx) saturate(1.85) contrast(1.04);
  overflow: hidden;
}

uni-tabbar .uni-tabbar::before {
  content: "";
  position: absolute;
  left: 26rpx;
  right: 26rpx;
  top: 8rpx;
  height: 24rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.70), rgba(255, 255, 255, 0.08));
  filter: blur(0.2rpx);
  pointer-events: none;
}

uni-tabbar .uni-tabbar::after {
  content: "";
  position: absolute;
  inset: 1rpx;
  border-radius: 39rpx;
  box-shadow:
    inset 0 0 24rpx rgba(255, 255, 255, 0.28),
    inset 16rpx 0 36rpx rgba(255, 255, 255, 0.16);
  pointer-events: none;
}

uni-tabbar .uni-tabbar-border {
  display: none !important;
}

uni-tabbar .uni-tabbar__item {
  position: relative;
  border-radius: 30rpx !important;
  overflow: hidden;
  color: #5f6e80;
  transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.85), color 0.18s ease;
}

uni-tabbar .uni-tabbar__item::before {
  content: "";
  position: absolute;
  inset: 6rpx 4rpx;
  border-radius: 30rpx;
  border: 1rpx solid rgba(255, 255, 255, 0);
  background: transparent;
  opacity: 0;
  transform: scale(0.92);
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.175, 0.885, 0.32, 1.85);
  pointer-events: none;
}

uni-tabbar .uni-tabbar__item:has(.uni-tabbar__label[style*="31, 68, 122"]) {
  color: #173b68;
}

uni-tabbar .uni-tabbar__item:has(.uni-tabbar__label[style*="31, 68, 122"])::before {
  opacity: 1;
  transform: scale(1);
  border-color: rgba(255, 255, 255, 0.72);
  background:
    radial-gradient(circle at 28% 10%, rgba(255, 255, 255, 0.70), transparent 38%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.36), rgba(255, 255, 255, 0.14));
  box-shadow:
    0 10rpx 24rpx rgba(25, 55, 98, 0.12),
    inset 1rpx 1rpx 1rpx rgba(255, 255, 255, 0.90),
    inset -1rpx -1rpx 1rpx rgba(255, 255, 255, 0.46),
    inset 0 -12rpx 24rpx rgba(197, 223, 255, 0.10);
  -webkit-backdrop-filter: blur(16rpx) saturate(1.7);
  backdrop-filter: blur(16rpx) saturate(1.7);
}

uni-tabbar .uni-tabbar__item:active {
  transform: scale(0.96);
}

uni-tabbar .uni-tabbar__bd {
  position: relative;
  z-index: 1;
  height: 106rpx !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8rpx !important;
}

uni-tabbar .uni-tabbar__bd::before {
  content: "";
  position: relative;
  display: block;
  width: 38rpx;
  height: 38rpx;
  color: currentColor;
  opacity: 0.86;
  box-sizing: border-box;
  background: transparent;
  transition: transform 0.2s ease, opacity 0.18s ease, color 0.18s ease;
}

uni-tabbar .uni-tabbar__bd::after {
  content: "";
  position: absolute;
  display: block;
  box-sizing: border-box;
  color: currentColor;
  pointer-events: none;
}

uni-tabbar .uni-tabbar__item:active .uni-tabbar__bd::before {
  transform: translateY(-2rpx) scale(1.06);
  opacity: 1;
}

uni-tabbar .uni-tabbar__item:nth-child(2) .uni-tabbar__bd::before {
  width: 30rpx;
  height: 23rpx;
  margin-top: 9rpx;
  border: 4rpx solid currentColor;
  border-top: 0;
  border-radius: 0 0 9rpx 9rpx;
  background: transparent;
}

uni-tabbar .uni-tabbar__item:nth-child(2) .uni-tabbar__bd::after {
  top: 21rpx;
  width: 25rpx;
  height: 25rpx;
  border-left: 4rpx solid currentColor;
  border-top: 4rpx solid currentColor;
  border-radius: 4rpx 0 0 0;
  transform: rotate(45deg);
}

uni-tabbar .uni-tabbar__item:nth-child(3) .uni-tabbar__bd::before {
  width: 34rpx;
  height: 32rpx;
  margin-top: 2rpx;
  border: 4rpx solid currentColor;
  border-radius: 10rpx;
  background:
    linear-gradient(currentColor, currentColor) 0 9rpx / 100% 4rpx no-repeat,
    linear-gradient(currentColor, currentColor) 9rpx 20rpx / 4rpx 4rpx no-repeat,
    linear-gradient(currentColor, currentColor) 19rpx 20rpx / 4rpx 4rpx no-repeat;
}

uni-tabbar .uni-tabbar__item:nth-child(3) .uni-tabbar__bd::after {
  top: 22rpx;
  width: 22rpx;
  height: 8rpx;
  border-left: 4rpx solid currentColor;
  border-right: 4rpx solid currentColor;
}

uni-tabbar .uni-tabbar__item:nth-child(4) .uni-tabbar__bd::before {
  width: 36rpx;
  height: 30rpx;
  margin-top: 2rpx;
  border: 4rpx solid currentColor;
  border-radius: 16rpx;
  background:
    linear-gradient(currentColor, currentColor) 10rpx 9rpx / 16rpx 4rpx no-repeat,
    linear-gradient(currentColor, currentColor) 10rpx 18rpx / 11rpx 4rpx no-repeat;
}

uni-tabbar .uni-tabbar__item:nth-child(5) .uni-tabbar__bd::before {
  width: 20rpx;
  height: 20rpx;
  margin-top: 2rpx;
  border: 4rpx solid currentColor;
  border-radius: 50%;
  background: transparent;
}

uni-tabbar .uni-tabbar__item:nth-child(5) .uni-tabbar__bd::after {
  top: 45rpx;
  width: 35rpx;
  height: 20rpx;
  border: 4rpx solid currentColor;
  border-bottom: 0;
  border-radius: 20rpx 20rpx 0 0;
}

uni-tabbar .uni-tabbar__label {
  position: relative;
  z-index: 1;
  margin-top: 4rpx !important;
  font-size: 20rpx !important;
  line-height: 1.1 !important;
  font-weight: 760 !important;
  text-shadow: 0 1rpx 1rpx rgba(255, 255, 255, 0.62);
}

uni-tabbar .uni-tabbar__item:has(.uni-tabbar__label[style*="31, 68, 122"]) .uni-tabbar__label {
  font-weight: 850 !important;
}

@keyframes glass-rise {
  from {
    opacity: 0;
    transform: translateY(18rpx) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes header-sheen {
  from {
    opacity: 0.52;
    transform: translateX(-18rpx) rotate(-11deg);
  }
  to {
    opacity: 0.88;
    transform: translateX(34rpx) rotate(-11deg);
  }
}

@keyframes soft-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5rpx);
  }
}

@media (prefers-reduced-motion: reduce) {
  .profile-card,
  .login-card,
  .search-box,
  .menu-grid,
  .filter-card,
  .mode-card,
  .section,
  .shortcut-card,
  .item-box,
  .order-item,
  .content-item,
  .assistant-row,
  .user-bubble {
    animation: none !important;
  }

  .top-action,
  .send-btn,
  .submit-btn,
  .login-btn,
  .logout-btn,
  .bottom-btn,
  .tool-btn,
  .memory-close,
  .mode-clear,
  .status-pill,
  .action-btn,
  .publish-btn {
    transition: none !important;
  }

  .app-top::before,
  .avatar-box,
  .avatar-wrap {
    animation: none !important;
  }
}
</style>
