<template>
  <view class="page">
    <view class="section">
      <text class="title">网络诊断</text>
      <text class="line">API: {{ config.baseURL }}</text>
      <text class="line">文件: {{ config.fileBaseURL }}</text>
      <text class="line">模式: {{ config.debug ? 'dev' : 'prod' }}</text>
    </view>

    <button class="button" :disabled="loading" @click="runDiagnose">
      {{ loading ? '检测中...' : '开始检测' }}
    </button>

    <view v-if="result" class="section">
      <text class="line">网络: {{ result.network.available ? '可用' : '不可用' }}</text>
      <text class="line">API: {{ result.api.reachable ? '成功' : '失败' }}</text>
      <text v-if="result.network.error" class="error">{{ result.network.error }}</text>
      <text v-if="result.api.error" class="error">{{ result.api.error }}</text>
      <text v-if="result.api.response" class="code">{{ JSON.stringify(result.api.response) }}</text>
    </view>
  </view>
</template>

<script>
import config from '@/utils/config.js'
import { diagnoseNetwork, printDiagnose } from '@/utils/diagnose.js'

export default {
  data() {
    return {
      config,
      loading: false,
      result: null
    }
  },
  onLoad() {
    this.runDiagnose()
  },
  methods: {
    async runDiagnose() {
      this.loading = true
      try {
        const result = await diagnoseNetwork()
        this.result = printDiagnose(result)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 48rpx 32rpx;
  background: #f7f8fa;
}

.section {
  padding: 28rpx;
  margin-bottom: 28rpx;
  background: #ffffff;
  border-radius: 16rpx;
}

.title {
  display: block;
  margin-bottom: 20rpx;
  color: #111827;
  font-size: 36rpx;
  font-weight: 700;
}

.line,
.error,
.code {
  display: block;
  margin-top: 12rpx;
  color: #374151;
  font-size: 26rpx;
  word-break: break-all;
}

.error {
  color: #dc2626;
}

.code {
  color: #047857;
}

.button {
  margin-bottom: 28rpx;
  color: #ffffff;
  background: #2563eb;
}
</style>
