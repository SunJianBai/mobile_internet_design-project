<template>
  <view class="chat-container">
    <view class="app-top">
      <button class="back-button" @click="goBack">
        <view class="back-chevron"></view>
      </button>
      <view class="title-row">
        <view>
          <text class="page-title">AI 助手</text>
          <text class="page-subtitle">活动推荐、地点查询、校园问询</text>
        </view>
        <button class="top-action" @click="handleCreateConversation">新对话</button>
      </view>
      <view class="toolbar">
        <picker
          class="conversation-picker"
          mode="selector"
          :range="conversationTitles"
          :value="currentConversationIndex"
          :disabled="!conversations.length"
          @change="handleConversationChange"
        >
          <view class="picker-view">
            <text class="picker-text">{{ currentConversationTitle }}</text>
            <view class="chevron"></view>
          </view>
        </picker>
        <button class="tool-btn subtle" hover-class="tool-btn-hover" @click="openMemoryPanel">记忆</button>
        <button class="tool-btn danger" hover-class="tool-btn-danger-hover" :disabled="!currentCid" @click="deleteCurrentConversation">删除</button>
      </view>
    </view>

    <scroll-view class="messages-scroll" scroll-y :scroll-top="scrollTop">
      <view
        v-for="msg in messages"
        :key="msg.mid || msg.localId"
        class="message-item"
        :class="{ user: msg.role === 'user' }"
      >
        <view v-if="msg.role === 'user'" class="user-bubble">
          <text class="user-message-text">{{ msg.content }}</text>
        </view>
        <view v-else class="assistant-row">
          <view class="assistant-avatar">AI</view>
          <view class="assistant-bubble">
            <view v-if="msg.operations && msg.operations.length" class="operation-timeline">
              <view
                v-for="overview in [getOperationOverview(msg)]"
                :key="`${msg.mid || msg.localId || 'msg'}-overview`"
                class="operation-overview"
                :class="overview.state"
              >
                <view class="operation-overview-main">
                  <view class="overview-status-dot" :class="overview.state"></view>
                  <view class="overview-copy">
                    <text class="overview-kicker">{{ overview.kicker }}</text>
                    <text class="overview-title">{{ overview.title }}</text>
                    <text v-if="overview.detail" class="overview-detail">{{ overview.detail }}</text>
                  </view>
                </view>
                <view class="overview-metrics">
                  <view v-for="metric in overview.metrics" :key="metric.label" class="overview-metric">
                    <text class="overview-metric-label">{{ metric.label }}</text>
                    <text class="overview-metric-value">{{ metric.value }}</text>
                  </view>
                </view>
              </view>
              <view v-if="!msg.loading && msg.content" class="operation-summary-head">
                <text>执行摘要</text>
                <text>{{ msg.operations.length }} 步</text>
              </view>
              <view
                v-for="(operation, opIndex) in msg.operations"
                :key="`${msg.mid || msg.localId || 'msg'}-${opIndex}`"
                class="operation-step"
                :class="operation.state || 'running'"
              >
                <view class="operation-dot"></view>
                <view class="operation-main">
                  <text class="operation-title">{{ operation.title }}</text>
                  <text v-if="operation.detail" class="operation-detail">{{ operation.detail }}</text>
                </view>
              </view>
            </view>
            <view v-if="msg.artifacts && msg.artifacts.length" class="artifact-list">
              <view
                v-for="(artifact, artifactIndex) in msg.artifacts"
                :key="`${msg.mid || msg.localId || 'msg'}-artifact-${artifactIndex}`"
                class="artifact-card"
                :class="`artifact-${artifact.type || 'generic'}`"
              >
                <view class="artifact-header">
                  <view class="artifact-icon">{{ getArtifactIcon(artifact) }}</view>
                  <view class="artifact-heading">
                    <text class="artifact-title">{{ artifact.title || '结果卡片' }}</text>
                    <text v-if="artifact.description" class="artifact-description">{{ artifact.description }}</text>
                  </view>
                </view>
                <view v-if="getArtifactHighlights(artifact).length" class="artifact-highlights">
                  <view
                    v-for="(highlight, highlightIndex) in getArtifactHighlights(artifact)"
                    :key="`${artifactIndex}-highlight-${highlightIndex}`"
                    class="artifact-highlight"
                  >
                    <text>{{ highlight.label }}</text>
                    <text class="artifact-highlight-value">{{ highlight.value }}</text>
                  </view>
                </view>
                <view v-if="artifact.items && artifact.items.length" class="artifact-result-list">
                  <button
                    v-for="(item, itemIndex) in artifact.items"
                    :key="`${artifactIndex}-item-${itemIndex}`"
                    class="artifact-result-item"
                    hover-class="artifact-result-item-hover"
                    :disabled="loading || !artifactItemHasAction(item)"
                    @click="handleArtifactItemAction(item)"
                  >
                    <view class="artifact-result-main">
                      <view class="artifact-result-title-row">
                        <text v-if="item.badge" class="artifact-result-badge">{{ item.badge }}</text>
                        <text class="artifact-result-title">{{ item.title || '结果项' }}</text>
                      </view>
                      <text v-if="item.subtitle" class="artifact-result-subtitle">{{ item.subtitle }}</text>
                    </view>
                    <view v-if="item.meta || item.actionLabel || item.hint" class="artifact-result-side">
                      <text v-if="item.meta" class="artifact-result-meta">{{ item.meta }}</text>
                      <text v-if="item.actionLabel" class="artifact-result-cta">{{ item.actionLabel }}</text>
                      <text v-if="item.hint" class="artifact-result-hint">{{ item.hint }}</text>
                    </view>
                  </button>
                </view>
                <view v-if="artifact.type === 'plan' && artifact.steps && artifact.steps.length" class="plan-step-list">
                  <view
                    v-for="(step, stepIndex) in artifact.steps"
                    :key="`plan-${artifactIndex}-${stepIndex}`"
                    class="plan-step"
                    :class="step.state || 'pending'"
                  >
                    <view class="plan-step-index">{{ stepIndex + 1 }}</view>
                    <view class="plan-step-main">
                      <text class="plan-step-title">{{ step.title || '执行步骤' }}</text>
                      <text v-if="step.detail" class="plan-step-detail">{{ step.detail }}</text>
                    </view>
                  </view>
                </view>
                <view v-if="artifact.fields && artifact.fields.length && !artifact.editing" class="artifact-fields">
                  <view
                    v-for="(field, fieldIndex) in artifact.fields"
                    :key="fieldIndex"
                    class="artifact-field"
                    :class="{ missing: isArtifactFieldMissing(field) }"
                  >
                    <text class="artifact-field-label">{{ field.label }}</text>
                    <text class="artifact-field-value">{{ formatArtifactValue(field.value) }}</text>
                  </view>
                </view>
                <view v-if="artifact.editing" class="artifact-editor">
                  <view
                    v-for="(field, fieldIndex) in artifact.fields"
                    :key="`edit-${fieldIndex}`"
                    class="artifact-edit-field"
                  >
                    <text class="artifact-field-label">{{ field.label }}</text>
                    <textarea
                      v-model="field.editValue"
                      class="artifact-edit-input"
                      auto-height
                      maxlength="500"
                      :placeholder="isArtifactFieldMissing(field) ? '补充这个信息' : '修改内容'"
                      @input="handleArtifactFieldInput(field, $event)"
                    />
                  </view>
                  <view v-if="artifactHasEmptyRequiredEdits(artifact)" class="artifact-edit-hint">
                    请先补充缺失信息，再保存或确认执行。
                  </view>
                </view>
                <view v-if="artifact.type === 'confirmation'" class="artifact-actions">
                  <template v-if="artifact.editing">
                    <button class="artifact-action" :disabled="isArtifactActionDisabled(artifact, 'save-edit')" @click.stop.prevent="requestArtifactAction(artifact, 'save-edit')">保存修改</button>
                    <button class="artifact-action primary" :disabled="isArtifactActionDisabled(artifact, 'confirm-edited')" @click.stop.prevent="requestArtifactAction(artifact, 'confirm-edited')">保存并确认</button>
                    <button class="artifact-action ghost" :disabled="isArtifactActionDisabled(artifact, 'cancel-edit')" @click.stop.prevent="requestArtifactAction(artifact, 'cancel-edit')">退出编辑</button>
                  </template>
                  <template v-else>
                    <button
                      class="artifact-action primary"
                      :disabled="isArtifactActionDisabled(artifact, artifactHasMissingFields(artifact) ? 'edit' : 'confirm')"
                      @click.stop.prevent="requestArtifactAction(artifact, artifactHasMissingFields(artifact) ? 'edit' : 'confirm')"
                    >
                      {{ artifactHasMissingFields(artifact) ? '补充信息' : '确认执行' }}
                    </button>
                    <button class="artifact-action" :disabled="isArtifactActionDisabled(artifact, 'edit')" @click.stop.prevent="requestArtifactAction(artifact, 'edit')">修改草稿</button>
                    <button class="artifact-action ghost" :disabled="isArtifactActionDisabled(artifact, 'cancel')" @click.stop.prevent="requestArtifactAction(artifact, 'cancel')">取消</button>
                  </template>
                </view>
                <view
                  v-else-if="artifact.actions && artifact.actions.length"
                  class="artifact-actions artifact-prompt-actions"
                  :class="{ 'guide-action-grid': isActionCardArtifact(artifact) }"
                >
                  <button
                    v-for="(action, actionIndex) in artifact.actions"
                    :key="`${artifactIndex}-action-${actionIndex}`"
                    class="artifact-action"
                    :class="{ primary: action.primary, 'guide-action-card': isActionCardArtifact(artifact) }"
                    :disabled="loading"
                    @click="handleArtifactPromptAction(action)"
                  >
                    <template v-if="isActionCardArtifact(artifact)">
                      <text class="guide-action-label">{{ action.label || '执行' }}</text>
                      <text v-if="action.prompt" class="guide-action-hint">{{ getGuideActionHint(action.prompt) }}</text>
                    </template>
                    <template v-else>{{ action.label || '执行' }}</template>
                  </button>
                </view>
              </view>
            </view>
            <view v-if="msg.loading && !msg.content" class="loading-dots">
              <view></view><view></view><view></view>
            </view>
            <text v-else-if="msg.status && !msg.content" class="status-text">{{ msg.status }}</text>
            <rich-text
              v-if="msg.content"
              class="markdown-body"
              :nodes="formatContent(msg.content)"
              @itemclick="handleRichTextItemClick"
            />
            <view v-if="getInteractiveMapCards(msg).length" class="inline-map-list">
              <view
                v-for="mapCard in getInteractiveMapCards(msg)"
                :key="mapCard.key"
                class="inline-map-card"
              >
                <view
                  class="inline-map-stage"
                  @touchstart.stop="startMapDrag(mapCard, $event)"
                  @touchmove.stop.prevent="moveMapDrag"
                  @touchend="endMapDrag"
                  @touchcancel="endMapDrag"
                  @mousedown.stop="startMapDrag(mapCard, $event)"
                  @mousemove.stop="moveMapDrag"
                  @mouseup="endMapDrag"
                  @mouseleave="endMapDrag"
                >
                  <view class="inline-map-grid" :style="mapCard.gridStyle">
                    <image
                      v-for="tile in mapCard.tiles"
                      :key="tile.key"
                      class="inline-map-tile"
                      :src="tile.src"
                      mode="widthFix"
                    />
                  </view>
                  <view class="inline-map-pin"><view class="inline-map-pin-dot"></view></view>
                  <text class="inline-map-badge">高德地图预览</text>
                  <view class="inline-map-controls">
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'zoom-in')">+</button>
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'zoom-out')">-</button>
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'north')">↑</button>
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'south')">↓</button>
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'west')">←</button>
                    <button class="inline-map-control" hover-class="inline-map-control-hover" @click.stop="adjustMapCard(mapCard, 'east')">→</button>
                  </view>
                </view>
                <view class="inline-map-meta">
                  <view class="inline-map-info">
                    <text class="inline-map-title">{{ mapCard.title }}</text>
                    <text class="inline-map-coords">{{ mapCard.lng.toFixed(6) }}, {{ mapCard.lat.toFixed(6) }} · zoom {{ mapCard.zoom }}</text>
                  </view>
                  <view class="inline-map-actions">
                    <button
                      class="inline-map-open inline-map-order"
                      hover-class="inline-map-order-hover"
                      :disabled="loading"
                      @click="createOrderDraftFromMap(mapCard)"
                    >
                      用此地点约伴
                    </button>
                    <button class="inline-map-open" hover-class="inline-map-open-hover" @click="openExternalUrl(mapCard.link)">打开高德地图</button>
                  </view>
                </view>
                <text class="inline-map-hint">可拖拽地图，也可以使用缩放和平移按钮。</text>
              </view>
            </view>
            <view v-if="getFollowupSuggestions(msg).length" class="reply-actions">
              <button
                v-for="suggestion in getFollowupSuggestions(msg)"
                :key="suggestion.label"
                class="reply-action"
                hover-class="reply-action-hover"
                :disabled="loading"
                @click="startSuggestedPrompt(suggestion.prompt)"
              >
                <text class="reply-action-icon">{{ suggestion.icon }}</text>
                <text class="reply-action-label">{{ suggestion.label }}</text>
              </button>
            </view>
          </view>
        </view>
      </view>

      <view v-if="messages.length === 0" class="empty-state">
        <view class="empty-logo">AI</view>
        <text class="empty-title">CampusHub AI 助手</text>
        <text class="empty-subtitle">选一个真实任务开始，AI 会先查询、整理草稿，并在发布前让你确认。</text>
        <view class="starter-grid">
          <button
            v-for="item in STARTER_PROMPTS"
            :key="item.title"
            class="starter-card"
            hover-class="starter-card-hover"
            :disabled="loading"
            @click="sendMessageText(item.prompt)"
          >
            <text class="starter-icon">{{ item.icon }}</text>
            <view class="starter-copy">
              <text class="starter-title">{{ item.title }}</text>
              <text class="starter-detail">{{ item.detail }}</text>
            </view>
          </button>
        </view>
      </view>
    </scroll-view>

    <view class="input-bar">
      <textarea
        v-model="inputText"
        class="input"
        auto-height
        maxlength="2000"
        placeholder="输入消息..."
        :disabled="loading"
        @input="saveDraft"
      />
      <button class="send-btn" :disabled="loading || !inputText.trim()" @click="sendMessage">
        {{ loading ? '发送中' : '发送' }}
      </button>
    </view>

    <view v-if="showMemoryPanel" class="memory-mask" @click="closeMemoryPanel"></view>
    <view v-if="showMemoryPanel" class="memory-panel">
      <view class="memory-header">
        <view class="memory-heading">
          <text class="memory-title">AI 记忆</text>
          <text class="memory-subtitle">{{ memoryPanelSubtitle }}</text>
        </view>
        <view class="memory-actions">
          <button class="memory-icon-btn" hover-class="memory-icon-btn-hover" :disabled="memoryLoading" @click.stop="loadMemories">刷新</button>
          <button class="memory-icon-btn ghost" hover-class="memory-icon-btn-hover" @click="closeMemoryPanel">关闭</button>
        </view>
      </view>
      <scroll-view class="memory-list" scroll-y>
        <view v-if="memoryLoading" class="memory-state">
          <view class="memory-spinner"></view>
          <view class="memory-state-copy">
            <text class="memory-state-title">正在加载记忆</text>
            <text class="memory-state-text">同步你确认保存过的偏好和上下文</text>
          </view>
        </view>
        <view v-else-if="memoryError" class="memory-state error">
          <text class="memory-state-icon">!</text>
          <view class="memory-state-copy">
            <text class="memory-state-title">加载失败</text>
            <text class="memory-state-text">{{ memoryError }}</text>
          </view>
          <button class="memory-retry" hover-class="memory-icon-btn-hover" @click.stop="loadMemories">重试</button>
        </view>
        <view v-else-if="memories.length === 0" class="memory-empty">
          <text class="memory-empty-icon">记</text>
          <text class="memory-empty-title">暂时没有 AI 记忆</text>
          <text class="memory-empty-text">只有经过你确认保存的偏好才会出现在这里。</text>
        </view>
        <view v-for="mem in memories" :key="mem.memId || mem.id" class="memory-item">
          <view class="memory-main">
            <text class="memory-tag">{{ mem.category || '偏好' }}</text>
            <text class="memory-content">{{ mem.content }}</text>
          </view>
          <button class="memory-delete" hover-class="memory-delete-hover" :disabled="deletingMemoryId === (mem.memId || mem.id)" @click="deleteMemory(mem)">
            {{ deletingMemoryId === (mem.memId || mem.id) ? '...' : '删除' }}
          </button>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { onLoad, onShow, onUnload } from '@dcloudio/uni-app'
import { aiApi } from '@/api/index.js'
import { showError, showSuccess } from '@/utils/util.js'

const DRAFT_KEY = 'ai_draft'
const STREAM_STATE_KEY = 'campushub_ai_stream_states'

const conversations = ref([])
const currentCid = ref(null)
const messages = ref([])
const memories = ref([])
const inputText = ref('')
const loading = ref(false)
const memoryLoading = ref(false)
const memoryError = ref('')
const deletingMemoryId = ref(null)
const showMemoryPanel = ref(false)
const scrollTop = ref(0)
const mapStates = ref({})

const STARTER_PROMPTS = [
  {
    icon: '图',
    title: '找附近地点',
    detail: '三个人足疗按摩，先看店',
    prompt: '我想要找3个人一起去洗脚按摩，有什么推荐的店吗'
  },
  {
    icon: '约',
    title: '查可加入约伴',
    detail: '今晚运动搭子，按校区筛选',
    prompt: '有没有今天晚上能加入的羽毛球约伴？良乡校区最好，帮我看看'
  },
  {
    icon: '查',
    title: '先查再建草稿',
    detail: '看完店铺后再确认发布',
    prompt: '先帮我找三家附近烤肉店，等我选了再创建约饭订单'
  },
  {
    icon: '稿',
    title: '发布前确认',
    detail: '整理动态草稿，不直接发布',
    prompt: '帮我发个动态：今晚八点三楼自习，缺搭子，看到的同学可以一起来'
  }
]

const uniqSuggestions = (items) => {
  const seen = new Set()
  return items
    .filter(item => {
      if (!item?.label || !item?.prompt || seen.has(item.label)) return false
      seen.add(item.label)
      return true
    })
    .slice(0, 4)
}

const getFollowupSuggestions = (message) => {
  if (!message || message.role !== 'assistant' || message.loading) return []

  const content = String(message.content || '')
  const artifacts = Array.isArray(message.artifacts) ? message.artifacts : []
  const hasConfirmation = artifacts.some(item => item.type === 'confirmation')
  if (hasConfirmation) {
    return uniqSuggestions([
      { icon: '改', label: '继续修改草稿', prompt: '我想继续修改这个草稿' },
      { icon: '补', label: '补充缺失信息', prompt: '我来补充这个草稿缺少的信息' },
      { icon: '查', label: '先再查一下', prompt: '先帮我再查一下相关信息，暂时不要执行' }
    ])
  }

  const suggestions = []
  const hasMap = /地图|附近|路线|店|餐厅|影院|按摩|地点|地址|map-card|高德|restaurant|cafe|cinema|massage/i.test(content)
  const hasWeather = /天气|温度|下雨|风|户外|跑步|出行|weather|rain|wind/i.test(content)
  const hasOrder = /约伴|订单|活动|报名|加入|篮球|羽毛球|自习|order|activity|join/i.test(content)
  const hasContent = /动态|评论|点赞|帖子|发布|post|comment/i.test(content)

  if (hasMap) {
    suggestions.push(
      { icon: '换', label: '换一批附近推荐', prompt: '换一批附近推荐，并继续展示地图' },
      { icon: '约', label: '基于地点约伴', prompt: '基于刚才推荐的地点，帮我整理一个约伴活动草稿' }
    )
  }
  if (hasWeather) {
    suggestions.push({ icon: '备', label: '给我备选安排', prompt: '如果天气不适合，帮我推荐一个室内备选安排' })
  }
  if (hasOrder) {
    suggestions.push(
      { icon: '筛', label: '只看可加入活动', prompt: '只筛选我现在还能加入的约伴活动' },
      { icon: '发', label: '帮我发起约伴', prompt: '帮我根据刚才的信息生成一个新的约伴活动草稿' }
    )
  }
  if (hasContent) {
    suggestions.push({ icon: '写', label: '整理成动态草稿', prompt: '把刚才的信息整理成一条校园动态草稿，先不要发布' })
  }

  if (!suggestions.length && content.trim()) {
    suggestions.push(
      { icon: '短', label: '再简短一点', prompt: '把刚才的回答再简短一点' },
      { icon: '细', label: '展开更多细节', prompt: '把刚才的回答展开得更具体一点' }
    )
  }

  return uniqSuggestions(suggestions)
}

let activeStreamController = null
let activeMapDrag = null
let streamStateSyncTimer = null

const AGENT_EVENT_TITLES = {
  agent_step: '智能体执行中',
  intent: '意图分析完成',
  tool_call: '调用工具',
  tool_start: '开始调用工具',
  tool_result: '工具调用完成',
  artifact: '生成结果卡片',
  confirm_required: '等待确认',
  status: '处理中'
}

const OPERATION_PHASE_LABELS = {
  intent: '意图',
  router: '路由',
  planning: '规划',
  order: '订单',
  content: '动态',
  map: '地图',
  weather: '天气',
  memory: '记忆',
  response: '回复',
  delegation_guard: '防循环',
  tool_call: '工具',
  tool_start: '工具',
  tool_result: '工具',
  artifact: '卡片',
  confirm_required: '确认',
  status: '状态'
}

const OPERATION_STATE_LABELS = {
  running: '执行中',
  pending: '待确认',
  completed: '已完成',
  failed: '异常'
}

const parseAgentEventData = (data) => {
  if (!data) return {}
  if (typeof data !== 'string') return data
  try {
    return JSON.parse(data)
  } catch (error) {
    return { title: data }
  }
}

const formatIntentDetail = (payload) => {
  const parts = []
  if (payload.primary_intent) parts.push(payload.primary_intent)
  if (payload.operation_type) parts.push(payload.operation_type)
  if (typeof payload.confidence === 'number') parts.push(`置信度 ${Math.round(payload.confidence * 100)}%`)
  if (payload.requires_confirmation) parts.push('需要确认')
  return parts.join(' · ')
}

const normalizeAgentOperation = (eventName, data) => {
  const payload = parseAgentEventData(data)
  const title = payload.title || AGENT_EVENT_TITLES[eventName] || eventName
  let detail = payload.detail || payload.summary || ''
  if (eventName === 'intent') {
    detail = formatIntentDetail(payload) || detail
  }
  return {
    eventName,
    phase: payload.phase || payload.domain || eventName,
    title,
    detail,
    state: payload.state || (eventName === 'confirm_required' ? 'pending' : 'running'),
    meta: {
      primaryIntent: payload.primary_intent,
      domain: payload.domain,
      operationType: payload.operation_type,
      confidence: payload.confidence,
      requiresConfirmation: payload.requires_confirmation
    }
  }
}

const getOperationPhaseLabel = (phase) => {
  const key = String(phase || '').toLowerCase()
  return OPERATION_PHASE_LABELS[key] || phase || '执行'
}

const getOperationOverview = (message) => {
  const operations = Array.isArray(message?.operations) ? message.operations : []
  const intentOperation = operations.find(item => item.eventName === 'intent' || item.meta?.primaryIntent)
  const failedCount = operations.filter(item => item.state === 'failed').length
  const pendingCount = operations.filter(item => item.state === 'pending').length
  const completedCount = operations.filter(item => (item.state || 'running') === 'completed').length
  const needsConfirmation = pendingCount > 0 || (message?.artifacts || []).some(item => item.type === 'confirmation')
  const state = failedCount
    ? 'failed'
    : (needsConfirmation ? 'pending' : (message?.loading ? 'running' : 'completed'))
  const latestActive = [...operations].reverse().find(item => ['running', 'pending'].includes(item.state))
  const latestCompleted = [...operations].reverse().find(item => item.state === 'completed')
  const latest = state === 'completed'
    ? (latestCompleted || operations[operations.length - 1] || {})
    : (latestActive || latestCompleted || operations[operations.length - 1] || {})
  const intentLabel = intentOperation?.meta?.primaryIntent || intentOperation?.phase || '识别中'
  const confidence = intentOperation?.meta?.confidence
  const effectiveCompletedCount = state === 'completed' ? operations.length : completedCount
  const metrics = [
    { label: '阶段', value: getOperationPhaseLabel(latest.phase || latest.eventName) },
    { label: '进度', value: `${effectiveCompletedCount}/${operations.length || 1}` }
  ]
  if (intentLabel) metrics.push({ label: '意图', value: intentLabel })
  if (typeof confidence === 'number') metrics.push({ label: '置信度', value: `${Math.round(confidence * 100)}%` })
  if (needsConfirmation) metrics.push({ label: '确认', value: '需要确认' })
  if (failedCount) metrics.push({ label: '异常', value: `${failedCount} 步` })

  return {
    state,
    kicker: OPERATION_STATE_LABELS[state] || '执行中',
    title: latest.title || (message?.loading ? '正在处理你的请求' : '执行已完成'),
    detail: latest.detail || (needsConfirmation ? '请检查确认卡片后再决定是否执行。' : ''),
    metrics: metrics.slice(0, 5)
  }
}

const normalizeArtifact = (eventName, data) => {
  const payload = parseAgentEventData(data)
  const type = payload.type || (eventName === 'confirm_required' ? 'confirmation' : 'generic')
  const fields = Array.isArray(payload.fields) ? payload.fields : []
  const steps = Array.isArray(payload.steps) ? payload.steps : []
  return {
    ...payload,
    type,
    fields: fields.map(field => {
      const normalized = field && typeof field === 'object' ? field : { label: '信息', value: field }
      const displayValue = formatArtifactValue(normalized.value)
      return {
        ...normalized,
        editValue: ['未填写', '待补充'].includes(displayValue) ? '' : displayValue
      }
    }),
    steps: steps
      .map(step => step && typeof step === 'object' ? step : { title: String(step || '') })
      .filter(step => step.title || step.detail),
    editing: false
  }
}

const getArtifactIcon = (artifact) => {
  if (artifact?.type === 'confirmation') return '!'
  if (artifact?.type === 'plan') return '计'
  if (artifact?.type === 'weather') return '天'
  if (artifact?.type === 'guide') return '行'
  if (artifact?.type === 'order') return '约'
  if (artifact?.type === 'content') return '动'
  return 'i'
}

const isActionCardArtifact = (artifact) => ['guide', 'weather', 'order', 'content'].includes(artifact?.type)

const truncateArtifactValue = (value, maxLength = 18) => {
  const text = String(value || '')
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

const getArtifactHighlights = (artifact) => {
  if (!['guide', 'weather', 'order', 'content', 'plan'].includes(artifact?.type)) return []
  const lowPriorityLabels = ['安全策略', '写操作保护', '摘要', '建议', '下一步', '结果预览']
  const fields = (artifact?.fields || [])
    .filter(field => field && field.label && !field.missing && !['未填写', '待补充'].includes(formatArtifactValue(field.value)))
  const primaryFields = fields.filter(field => !lowPriorityLabels.includes(String(field.label)))
  const selected = (primaryFields.length ? primaryFields : fields).slice(0, 3)
  return selected.map(field => ({
    label: field.label,
    value: truncateArtifactValue(formatArtifactValue(field.value))
  }))
}

const readStreamStates = () => {
  try {
    return JSON.parse(uni.getStorageSync(STREAM_STATE_KEY) || '{}')
  } catch (error) {
    return {}
  }
}

const writeStreamStates = (states) => {
  try {
    uni.setStorageSync(STREAM_STATE_KEY, JSON.stringify(states || {}))
  } catch (error) {
    // ignore storage failures
  }
}

const getStoredStreamState = (cid) => {
  if (!cid) return null
  return readStreamStates()[String(cid)] || null
}

const toPlainStreamValue = (value, fallback) => {
  try {
    return JSON.parse(JSON.stringify(value ?? fallback))
  } catch (error) {
    return fallback
  }
}

const snapshotAssistantMessage = (message, state = 'running') => ({
  mid: message.mid,
  localId: message.localId,
  role: 'assistant',
  content: message.content || '',
  status: message.status || '',
  loading: state === 'running',
  operations: toPlainStreamValue(message.operations, []),
  artifacts: toPlainStreamValue(message.artifacts, [])
})

const saveStreamState = (cid, assistantMsg, userText, state = 'running') => {
  if (!cid || !assistantMsg) return
  const states = readStreamStates()
  states[String(cid)] = {
    cid,
    state,
    userText,
    updatedAt: Date.now(),
    assistant: snapshotAssistantMessage(assistantMsg, state)
  }
  writeStreamStates(states)
}

const clearStreamState = (cid) => {
  if (!cid) return
  const states = readStreamStates()
  delete states[String(cid)]
  writeStreamStates(states)
}

const appendStoredStreamMessage = (cid) => {
  const stored = getStoredStreamState(cid)
  if (!stored?.assistant) return false

  const restoredMessage = {
    ...stored.assistant,
    loading: stored.state === 'running',
    restored: true
  }
  const index = messages.value.findIndex(item =>
    (restoredMessage.mid && item.mid === restoredMessage.mid) ||
    (restoredMessage.localId && item.localId === restoredMessage.localId) ||
    (item.restored && item.role === 'assistant')
  )
  if (index >= 0) {
    Object.assign(messages.value[index], restoredMessage)
  } else {
    messages.value.push(restoredMessage)
  }
  nextTick(scrollToBottom)
  return true
}

const syncStoredStreamMessage = () => {
  if (!currentCid.value) return
  appendStoredStreamMessage(currentCid.value)
}

const applyAgentArtifact = (message, eventName, data) => {
  if (!message.artifacts) message.artifacts = []
  const artifact = normalizeArtifact(eventName, data)
  const key = artifact.id || `${artifact.type}:${artifact.title || ''}:${artifact.actionKind || ''}`
  const exists = message.artifacts.some(item => (item.id || `${item.type}:${item.title || ''}:${item.actionKind || ''}`) === key)
  if (!exists) {
    message.artifacts.push(artifact)
  }
}

const applyAgentEvent = (message, eventName, data) => {
  if (!message.operations) message.operations = []
  const operation = normalizeAgentOperation(eventName, data)
  const previous = [...message.operations].reverse().find(item => item.phase === operation.phase && item.eventName === operation.eventName)
  if (previous && operation.state !== 'running') {
    previous.title = operation.title
    previous.detail = operation.detail
    previous.state = operation.state
  } else {
    message.operations.push(operation)
  }
  if (operation.state === 'running' || operation.state === 'pending') {
    message.status = operation.title
  }
  if (eventName === 'confirm_required' || eventName === 'artifact') {
    applyAgentArtifact(message, eventName, data)
  }
}

const formatArtifactValue = (value) => {
  if (value === null || value === undefined || value === '') return '未填写'
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const isArtifactFieldMissing = (field) => {
  if (field?.missing) return true
  return ['未填写', '待补充'].includes(formatArtifactValue(field?.value))
}

const artifactHasMissingFields = (artifact) => {
  return (artifact?.fields || []).some(isArtifactFieldMissing)
}

const artifactHasEmptyRequiredEdits = (artifact) => {
  return (artifact?.fields || []).some(field =>
    isArtifactFieldMissing(field) && !String(field.editValue ?? '').trim()
  )
}

const applyArtifactEdits = (artifact) => {
  if (!artifact?.fields?.length) return true
  if (artifactHasEmptyRequiredEdits(artifact)) {
    showError('请先补充草稿中的缺失信息')
    return false
  }
  artifact.fields = artifact.fields.map(field => {
    const nextValue = String(field.editValue ?? '').trim()
    const updated = { ...field }
    if (nextValue) {
      updated.value = nextValue
      updated.missing = false
    } else if (!isArtifactFieldMissing(field)) {
      updated.value = ''
    }
    updated.editValue = nextValue
    return updated
  })
  artifact.missingFields = (artifact.missingFields || [])
    .filter(label => artifact.fields.some(field =>
      String(field.label || '') === String(label || '') && isArtifactFieldMissing(field)
    ))
  return true
}

const conversationTitles = computed(() => {
  if (!conversations.value.length) return ['暂无对话']
  return conversations.value.map(item => item.title || `会话 ${item.cid}`)
})

const currentConversationIndex = computed(() => {
  const index = conversations.value.findIndex(item => item.cid === currentCid.value)
  return index >= 0 ? index : 0
})

const currentConversationTitle = computed(() => {
  if (!conversations.value.length) return '暂无对话'
  return conversationTitles.value[currentConversationIndex.value]
})

const memoryPanelSubtitle = computed(() => {
  if (memoryLoading.value) return '正在同步'
  if (memoryError.value) return '需要重试'
  return memories.value.length ? `${memories.value.length} 条长期记忆` : '发布前确认后才会保存'
})

const normalizeList = (value) => {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.records)) return value.records
  if (Array.isArray(value?.list)) return value.list
  return []
}

const ensureLogin = () => {
  const userId = uni.getStorageSync('userId')
  if (!userId) {
    showError('请先登录')
    uni.navigateTo({ url: '/pages/auth/login' })
    return false
  }
  return true
}

const scrollToBottom = () => {
  nextTick(() => {
    scrollTop.value = scrollTop.value + 1
    setTimeout(() => {
      scrollTop.value = 999999
    }, 80)
  })
}

const saveDraft = () => {
  uni.setStorageSync(DRAFT_KEY, inputText.value)
}

const clearDraft = () => {
  uni.removeStorageSync(DRAFT_KEY)
}

const goBack = () => {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.switchTab({ url: '/pages/index/index' })
}

const loadMessages = async (cid) => {
  if (!cid) {
    messages.value = []
    return
  }

  const list = await aiApi.getMessages(cid)
  const normalizedMessages = normalizeList(list)
  messages.value = normalizedMessages.map(item => ({
    ...item,
    role: item.role || 'assistant',
    content: item.content || item.message || ''
  }))
  const stored = getStoredStreamState(cid)
  const latestSaved = normalizedMessages[normalizedMessages.length - 1]
  if (stored && (latestSaved?.role || 'assistant') === 'assistant' && (latestSaved?.content || latestSaved?.message)) {
    clearStreamState(cid)
  } else if (stored && Date.now() - Number(stored.updatedAt || 0) < 10 * 60 * 1000) {
    appendStoredStreamMessage(cid)
  } else if (stored) {
    clearStreamState(cid)
  }
  scrollToBottom()
}

const switchConversation = async (cid) => {
  currentCid.value = cid
  await loadMessages(cid)
}

const loadConversations = async (selectFirst = false, { reloadCurrent = true } = {}) => {
  if (!ensureLogin()) return

  const list = await aiApi.listConversations()
  conversations.value = normalizeList(list)

  const currentExists = conversations.value.some(item => item.cid === currentCid.value)
  if (currentCid.value && currentExists) {
    if (reloadCurrent) {
      await loadMessages(currentCid.value)
    }
    return
  }

  const firstCid = conversations.value[0]?.cid
  if (selectFirst && firstCid) {
    await switchConversation(firstCid)
  } else {
    currentCid.value = null
    messages.value = []
  }
}

const createConversation = async () => {
  if (!ensureLogin()) return null

  const conversation = await aiApi.createConversation()
  if (!conversation?.cid) {
    throw new Error('创建会话失败')
  }

  conversations.value = [
    conversation,
    ...conversations.value.filter(item => item.cid !== conversation.cid)
  ]
  await switchConversation(conversation.cid)
  return conversation.cid
}

const handleCreateConversation = async () => {
  try {
    await createConversation()
  } catch (error) {
    showError(error.message || '创建会话失败')
  }
}

const deleteCurrentConversation = () => {
  if (!currentCid.value) return

  uni.showModal({
    title: '删除对话',
    content: '确定删除当前 AI 对话吗？',
    success: async (res) => {
      if (!res.confirm) return

      try {
        const deletedCid = currentCid.value
        await aiApi.deleteConversation(deletedCid)
        showSuccess('已删除')

        conversations.value = conversations.value.filter(item => item.cid !== deletedCid)
        const nextCid = conversations.value[0]?.cid
        if (nextCid) {
          await switchConversation(nextCid)
        } else {
          currentCid.value = null
          messages.value = []
        }
      } catch (error) {
        showError(error.message || '删除失败')
      }
    }
  })
}

const handleConversationChange = async (e) => {
  const conversation = conversations.value[e.detail.value]
  if (!conversation) return

  try {
    await switchConversation(conversation.cid)
  } catch (error) {
    showError(error.message || '加载消息失败')
  }
}

const sendMessageText = async (text) => {
  if (!text || loading.value) return
  inputText.value = text
  await nextTick()
  await sendMessage()
}

const startSuggestedPrompt = async (prompt) => {
  if (!prompt || loading.value) return
  await sendMessageText(prompt)
}

const persistCurrentArtifactMessage = () => {
  const cid = currentCid.value
  const stored = getStoredStreamState(cid)
  if (!cid || !stored?.assistant) return
  const assistant = messages.value.find(item =>
    (stored.assistant.mid && item.mid === stored.assistant.mid) ||
    (stored.assistant.localId && item.localId === stored.assistant.localId) ||
    (item.restored && item.role === 'assistant')
  )
  if (!assistant) return
  const states = readStreamStates()
  states[String(cid)] = {
    ...stored,
    updatedAt: Date.now(),
    assistant: snapshotAssistantMessage(assistant, stored.state || 'completed')
  }
  writeStreamStates(states)
}

const refreshArtifactMessages = () => {
  messages.value = messages.value.map(message => ({
    ...message,
    artifacts: Array.isArray(message.artifacts)
      ? message.artifacts.map(artifact => ({
          ...artifact,
          fields: Array.isArray(artifact.fields)
            ? artifact.fields.map(field => ({ ...field }))
            : artifact.fields,
          actions: Array.isArray(artifact.actions) ? [...artifact.actions] : artifact.actions,
          steps: Array.isArray(artifact.steps) ? [...artifact.steps] : artifact.steps,
          items: Array.isArray(artifact.items) ? artifact.items.map(item => ({ ...item })) : artifact.items
        }))
      : message.artifacts
  }))
  persistCurrentArtifactMessage()
}

const getInputEventValue = (event) => {
  if (event?.detail && Object.prototype.hasOwnProperty.call(event.detail, 'value')) {
    return event.detail.value
  }
  if (event?.target && Object.prototype.hasOwnProperty.call(event.target, 'value')) {
    return event.target.value
  }
  return ''
}

const handleArtifactFieldInput = (field, event) => {
  field.editValue = String(getInputEventValue(event) ?? '')
  refreshArtifactMessages()
}

const handleArtifactAction = (artifact, action) => {
  const title = artifact?.title || '这个草稿'
  if (action === 'edit') {
    artifact.editing = true
    artifact.fields = (artifact.fields || []).map(field => ({
      ...field,
      editValue: field.editValue ?? (
        ['未填写', '待补充'].includes(formatArtifactValue(field.value))
          ? ''
          : formatArtifactValue(field.value)
      )
    }))
    refreshArtifactMessages()
    return
  }
  if (action === 'cancel-edit') {
    artifact.editing = false
    refreshArtifactMessages()
    return
  }
  if (action === 'save-edit') {
    if (!applyArtifactEdits(artifact)) return
    artifact.editing = false
    refreshArtifactMessages()
    showSuccess('草稿已更新，请确认后执行')
    return
  }
  if (action === 'confirm-edited') {
    if (!applyArtifactEdits(artifact)) return
    artifact.editing = false
    refreshArtifactMessages()
    sendMessageText(buildArtifactConfirmMessage(artifact, true))
    return
  }
  if (action === 'confirm') {
    if (artifactHasMissingFields(artifact)) {
      showError('请先点击修改草稿补充缺失信息')
      return
    }
    sendMessageText(buildArtifactConfirmMessage(artifact, false))
    return
  }
  if (action === 'cancel') {
    sendMessageText(artifact?.cancelMessage || `取消这个草稿：${title}`)
  }
}

const isArtifactActionDisabled = (artifact, action) => {
  if (loading.value) return true
  if (['save-edit', 'confirm-edited'].includes(action)) {
    return artifactHasEmptyRequiredEdits(artifact)
  }
  if (action === 'confirm') {
    return artifactHasMissingFields(artifact)
  }
  return false
}

const requestArtifactAction = (artifact, action) => {
  if (isArtifactActionDisabled(artifact, action)) return
  handleArtifactAction(artifact, action)
}

const buildArtifactConfirmMessage = (artifact, edited = false) => {
  const title = artifact?.title || '这个草稿'
  const fields = (artifact?.fields || [])
    .map(field => {
      const value = edited
        ? String(field.editValue ?? '').trim()
        : formatArtifactValue(field.value)
      return value ? `${field.label}: ${value}` : ''
    })
    .filter(Boolean)
  const fieldText = fields.length ? `\n${fields.join('\n')}` : ''
  const prefix = edited ? '我确认按修改后的内容执行这个草稿' : '我确认执行这个草稿'
  return `${prefix}：${title}${fieldText}`
}

const handleArtifactPromptAction = (action) => {
  const route = String(action?.route || '').trim()
  if (route) {
    const appRoute = mapWebRouteToApp(route)
    if (appRoute) {
      if (appRoute.type === 'tab') {
        uni.switchTab({ url: appRoute.url })
      } else {
        uni.navigateTo({ url: appRoute.url })
      }
      return
    }
  }
  const prompt = String(action?.prompt || '').trim()
  if (prompt) {
    sendMessageText(prompt)
  }
}

const artifactItemHasAction = (item) => {
  return Boolean(String(item?.route || '').trim() || String(item?.prompt || '').trim())
}

const handleArtifactItemAction = (item) => {
  if (!artifactItemHasAction(item)) return
  handleArtifactPromptAction(item)
}

const getGuideActionHint = (prompt) => {
  const text = String(prompt || '').replace(/\s+/g, ' ').trim()
  return text.length > 32 ? `${text.slice(0, 32)}...` : text
}

const streamAssistantReply = (cid, userMessage, assistantMsg) => {
  return new Promise((resolve) => {
    let settled = false
    const finish = (streamed) => {
      if (settled) return
      settled = true
      activeStreamController = null
      resolve(streamed)
    }

    const controller = aiApi.streamMessage(cid, userMessage, {
      onStatus(statusText) {
        assistantMsg.loading = false
        applyAgentEvent(assistantMsg, 'status', statusText || '正在处理...')
        saveStreamState(cid, assistantMsg, userMessage)
        scrollToBottom()
      },
      onEvent(eventName, data) {
        assistantMsg.loading = false
        applyAgentEvent(assistantMsg, eventName, data)
        saveStreamState(cid, assistantMsg, userMessage)
        scrollToBottom()
      },
      onDelta(text) {
        assistantMsg.loading = false
        assistantMsg.status = ''
        assistantMsg.content += text
        saveStreamState(cid, assistantMsg, userMessage)
        scrollToBottom()
      },
      onDone() {
        assistantMsg.loading = false
        if (!assistantMsg.content) {
          assistantMsg.content = '抱歉，AI 未返回有效内容。'
        }
        clearStreamState(cid)
        finish(true)
      },
      onError(errorText) {
        assistantMsg.loading = false
        if (assistantMsg.content) {
          assistantMsg.content += `\n\n错误：${errorText || '流式回复中断'}`
          saveStreamState(cid, assistantMsg, userMessage, 'error')
          finish(true)
        } else {
          saveStreamState(cid, assistantMsg, userMessage, 'error')
          finish(false)
        }
      }
    })

    if (!controller) {
      finish(false)
      return
    }

    activeStreamController = controller
  })
}

const sendMessage = async () => {
  const userMessage = inputText.value.trim()
  if (!userMessage || loading.value) return
  if (!ensureLogin()) return

  try {
    if (!currentCid.value) {
      await createConversation()
    }
    if (!currentCid.value) return
  } catch (error) {
    showError(error.message || '创建会话失败')
    return
  }

  inputText.value = ''
  clearDraft()

  const assistantLocalId = `local-assistant-${Date.now()}`
  const assistantMsg = {
    localId: assistantLocalId,
    role: 'assistant',
    content: '',
    status: '正在思考...',
    loading: true,
    operations: [],
    artifacts: []
  }

  messages.value.push({
    localId: `local-user-${Date.now()}`,
    role: 'user',
    content: userMessage
  })
  messages.value.push(assistantMsg)
  applyAgentEvent(assistantMsg, 'agent_step', JSON.stringify({
    phase: 'client',
    title: '已发送消息',
    detail: '正在建立 AI 流式连接并等待智能体调度',
    state: 'running'
  }))
  saveStreamState(currentCid.value, assistantMsg, userMessage)
  scrollToBottom()

  loading.value = true
  try {
    const sentCid = currentCid.value
    const streamed = await streamAssistantReply(sentCid, userMessage, assistantMsg)

    if (!streamed) {
      assistantMsg.loading = true
      assistantMsg.status = '正在生成回复...'
      const reply = await aiApi.sendMessage(sentCid, userMessage)
      assistantMsg.mid = reply?.mid
      assistantMsg.loading = false
      assistantMsg.status = ''
      assistantMsg.content = reply?.content || reply?.message || 'AI 未返回有效内容'
      clearStreamState(sentCid)
    }

    await loadConversations(false, { reloadCurrent: false })
  } catch (error) {
    assistantMsg.loading = false
    assistantMsg.status = ''
    assistantMsg.content = error.message || 'AI 服务暂时不可用'
    saveStreamState(currentCid.value, assistantMsg, userMessage, 'error')
    showError(error.message || 'AI 回复失败')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const loadMemories = async () => {
  memoryLoading.value = true
  memoryError.value = ''
  try {
    const list = await aiApi.getMemories()
    memories.value = normalizeList(list)
  } catch (error) {
    memoryError.value = error.message || '加载记忆失败'
    showError(memoryError.value)
  } finally {
    memoryLoading.value = false
  }
}

const openMemoryPanel = async () => {
  if (!ensureLogin()) return

  showMemoryPanel.value = true
  await loadMemories()
}

const closeMemoryPanel = () => {
  showMemoryPanel.value = false
}

const deleteMemory = (mem) => {
  const memoryId = mem.memId || mem.id
  if (!memoryId || deletingMemoryId.value) return

  uni.showModal({
    title: '删除记忆',
    content: '确定删除这条 AI 记忆吗？',
    success: async (res) => {
      if (!res.confirm) return

      try {
        deletingMemoryId.value = memoryId
        await aiApi.deleteMemory(memoryId)
        memories.value = memories.value.filter(item => (item.memId || item.id) !== memoryId)
        showSuccess('已删除')
      } catch (error) {
        showError(error.message || '删除失败')
      } finally {
        deletingMemoryId.value = null
      }
    }
  })
}

const escapeHtml = (unsafe) => {
  return (unsafe || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const sanitizeUrl = (url) => {
  const value = String(url || '').trim()
  if (!value) return ''
  if (/^javascript:/i.test(value)) return ''
  return value
}

const parseMapAttrs = (attrs = '') => {
  const props = {}
  const normalizedAttrs = String(attrs || '')
    .replace(/\s*(lng|lat|zoom|title|name)=/g, ' $1=')
    .trim()
  normalizedAttrs.replace(/(\w+)=("[^"]*"|'[^']*'|.*?)(?=\s+\w+=|$)/g, (match, key, value) => {
    props[key] = String(value || '').replace(/^["']|["']$/g, '').trim()
    return match
  })
  ;['lng', 'lat', 'zoom'].forEach((key) => {
    const match = attrs.match(new RegExp(`${key}=(-?\\d+(?:\\.\\d+)?)`))
    if (match) props[key] = match[1]
  })
  const titleMatch =
    attrs.match(/(?:^|\s)title=("[^"]*"|'[^']*'|.+?)(?=\s+\w+=|$)/) ||
    attrs.match(/title=("[^"]*"|'[^']*'|.+)$/)
  if (titleMatch) {
    props.title = titleMatch[1].replace(/^["']|["']$/g, '').trim()
  }
  return props
}

const clampNumber = (value, min, max) => Math.min(max, Math.max(min, value))

const lngLatToTilePoint = (lng, lat, zoom) => {
  const latRad = (lat * Math.PI) / 180
  const scale = 2 ** zoom
  return {
    x: ((lng + 180) / 360) * scale,
    y: ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * scale
  }
}

const getAmapTileUrl = (x, y, z) => {
  const server = Math.abs(x + y) % 4 + 1
  return `https://webrd0${server}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x=${x}&y=${y}&z=${z}`
}

const tilePointToLngLat = (x, y, zoom) => {
  const scale = 2 ** zoom
  const lng = (x / scale) * 360 - 180
  const n = Math.PI - (2 * Math.PI * y) / scale
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))
  return { lng, lat }
}

const buildMapTileGrid = (lng, lat, zoom) => {
  const tilePoint = lngLatToTilePoint(lng, lat, zoom)
  const baseX = Math.floor(tilePoint.x)
  const baseY = Math.floor(tilePoint.y)
  const startX = baseX - 1
  const startY = baseY - 1
  const pointX = Math.round((tilePoint.x - startX) * 256)
  const pointY = Math.round((tilePoint.y - startY) * 256)
  const tiles = []

  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const x = startX + col
      const y = startY + row
      tiles.push({ key: `${zoom}-${x}-${y}`, src: getAmapTileUrl(x, y, zoom) })
    }
  }

  return {
    tiles,
    gridStyle: `left:calc(50% - ${pointX}px);top:calc(50% - ${pointY}px);`
  }
}

const getMessageKey = (msg) => String(msg?.mid || msg?.localId || 'message')

const extractMapProps = (content = '') => {
  const cards = []
  String(content || '').replace(/:{2,}map\{([^}]+)\}/g, (match, attrs) => {
    const props = parseMapAttrs(attrs)
    const lng = Number.parseFloat(props.lng)
    const lat = Number.parseFloat(props.lat)
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      cards.push({
        lng,
        lat,
        zoom: clampNumber(Number.parseInt(props.zoom || '15', 10) || 15, 3, 18),
        title: props.title || props.name || '位置'
      })
    }
    return match
  })
  return cards
}

const getInteractiveMapCards = (msg) => {
  return extractMapProps(msg?.content).map((props, index) => {
    const key = `${getMessageKey(msg)}-${index}`
    const current = mapStates.value[key] || props
    const grid = buildMapTileGrid(current.lng, current.lat, current.zoom)
    const link = `https://uri.amap.com/marker?position=${current.lng},${current.lat}&name=${encodeURIComponent(current.title)}&coordinate=gaode&callnative=0`
    return { key, ...current, ...grid, link }
  })
}

const buildMapOrderDraftPrompt = (card) => {
  const title = String(card?.title || '这个地点').trim()
  const lng = Number.isFinite(card?.lng) ? card.lng.toFixed(6) : ''
  const lat = Number.isFinite(card?.lat) ? card.lat.toFixed(6) : ''
  const coords = lng && lat ? `${lng}, ${lat}` : '未提供'
  return [
    '我想基于刚才查询到的这个地点创建一个约伴订单草稿。',
    '请先生成可编辑确认卡片，等我确认后再执行，不要直接发布。',
    `地点：${title}`,
    `坐标：${coords}`,
    '请结合上文的人数、活动类型、时间偏好和校区信息；如果缺少订单必填项，请先让我补充。'
  ].join('\n')
}

const createOrderDraftFromMap = (card) => {
  if (loading.value || !card) return
  sendMessageText(buildMapOrderDraftPrompt(card))
}

const setMapCardState = (key, nextState) => {
  const state = mapStates.value[key] || nextState
  mapStates.value = {
    ...mapStates.value,
    [key]: {
      ...state,
      title: nextState.title || state.title || '位置',
      lng: clampNumber(nextState.lng, -180, 180),
      lat: clampNumber(nextState.lat, -85, 85),
      zoom: clampNumber(Math.round(nextState.zoom), 3, 18)
    }
  }
}

const adjustMapCard = (card, action) => {
  if (!card?.key || !action) return
  if (action === 'zoom-in') return setMapCardState(card.key, { ...card, zoom: card.zoom + 1 })
  if (action === 'zoom-out') return setMapCardState(card.key, { ...card, zoom: card.zoom - 1 })

  const point = lngLatToTilePoint(card.lng, card.lat, card.zoom)
  const step = 0.45
  const moves = {
    north: { x: 0, y: -step },
    south: { x: 0, y: step },
    west: { x: -step, y: 0 },
    east: { x: step, y: 0 }
  }
  const move = moves[action]
  if (!move) return
  const next = tilePointToLngLat(point.x + move.x, point.y + move.y, card.zoom)
  setMapCardState(card.key, { ...card, ...next })
}

const getPointerXY = (event) => {
  const touch = event?.touches?.[0] || event?.changedTouches?.[0]
  if (touch) return { x: touch.clientX, y: touch.clientY }
  return { x: event?.clientX || 0, y: event?.clientY || 0 }
}

const startMapDrag = (card, event) => {
  if (!card?.key) return
  const point = getPointerXY(event)
  activeMapDrag = {
    key: card.key,
    startX: point.x,
    startY: point.y,
    zoom: card.zoom,
    startPoint: lngLatToTilePoint(card.lng, card.lat, card.zoom),
    title: card.title
  }
}

const moveMapDrag = (event) => {
  if (!activeMapDrag) return
  const point = getPointerXY(event)
  const dx = (point.x - activeMapDrag.startX) / 256
  const dy = (point.y - activeMapDrag.startY) / 256
  const next = tilePointToLngLat(activeMapDrag.startPoint.x - dx, activeMapDrag.startPoint.y - dy, activeMapDrag.zoom)
  setMapCardState(activeMapDrag.key, {
    title: activeMapDrag.title,
    zoom: activeMapDrag.zoom,
    ...next
  })
}

const endMapDrag = () => {
  activeMapDrag = null
}

const renderMapCard = (props = {}) => {
  const lng = Number.parseFloat(props.lng)
  const lat = Number.parseFloat(props.lat)
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return ''

  const zoom = clampNumber(Number.parseInt(props.zoom || '15', 10) || 15, 3, 18)
  const title = props.title || props.name || '位置'
  const tilePoint = lngLatToTilePoint(lng, lat, zoom)
  const baseX = Math.floor(tilePoint.x)
  const baseY = Math.floor(tilePoint.y)
  const startX = baseX - 1
  const startY = baseY - 1
  const pointX = Math.round((tilePoint.x - startX) * 256)
  const pointY = Math.round((tilePoint.y - startY) * 256)
  const tiles = []

  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const x = startX + col
      const y = startY + row
      tiles.push(`<img class="map-tile" alt="" src="${getAmapTileUrl(x, y, zoom)}" />`)
    }
  }

  const amapLink = `https://uri.amap.com/marker?position=${lng},${lat}&name=${encodeURIComponent(title)}&coordinate=gaode&callnative=0`
  return `<div class="map-card">` +
    `<div class="map-tile-stage">` +
      `<div class="map-tile-grid" style="left:calc(50% - ${pointX}px);top:calc(50% - ${pointY}px);">${tiles.join('')}</div>` +
      `<span class="map-pin"><span class="map-pin-dot"></span></span>` +
      `<span class="map-badge">高德地图预览</span>` +
    `</div>` +
    `<div class="map-card-meta">` +
      `<span class="map-card-info">` +
        `<strong class="map-card-title">${escapeHtml(title)}</strong>` +
        `<span class="map-card-coords">${lng.toFixed(6)}, ${lat.toFixed(6)} · zoom ${zoom}</span>` +
      `</span>` +
      `<a href="${escapeHtml(amapLink)}" class="map-card-action">打开高德地图</a>` +
    `</div>` +
  `</div>`
}

const renderEntityLinkCard = (url = '', text = '') => {
  const orderDetail = url.match(/^\/orders\/(\d+)$/)
  const contentDetail = url.match(/^\/contents\/(\d+)$/)
  let meta = null

  if (orderDetail) {
    meta = {
      type: 'order',
      icon: '约',
      title: text || `订单 #${orderDetail[1]}`,
      subtitle: `约伴订单 #${orderDetail[1]}`,
      action: '查看详情'
    }
  } else if (contentDetail) {
    meta = {
      type: 'content',
      icon: '动',
      title: text || `动态 #${contentDetail[1]}`,
      subtitle: `校园动态 #${contentDetail[1]}`,
      action: '查看详情'
    }
  } else if (url === '/orders') {
    meta = {
      type: 'order',
      icon: '约',
      title: text || '查看约伴活动',
      subtitle: '浏览可加入的校园约伴订单',
      action: '打开列表'
    }
  } else if (url === '/contents') {
    meta = {
      type: 'content',
      icon: '动',
      title: text || '查看校园动态',
      subtitle: '浏览同学发布的校园动态',
      action: '打开列表'
    }
  }

  if (!meta) return ''
  return `<a href="${escapeHtml(url)}" data-route="${escapeHtml(url)}" class="app-link entity-link-card entity-${meta.type}">` +
    `<span class="entity-icon">${meta.icon}</span>` +
    `<span class="entity-main">` +
      `<strong class="entity-title">${meta.title}</strong>` +
      `<span class="entity-subtitle">${meta.subtitle}</span>` +
    `</span>` +
    `<span class="entity-action">${meta.action}</span>` +
  `</a>`
}

const renderMarkdown = (source) => {
  if (!source) return ''

  let md = source
  const mapBlocks = []
  md = md.replace(/:{2,}map\{([^}]+)\}/g, (match, attrs) => {
    const idx = mapBlocks.length
    mapBlocks.push(parseMapAttrs(attrs))
    return `@@MAP_BLOCK_${idx}@@`
  })

  const codeBlocks = []
  md = md.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    const idx = codeBlocks.length
    codeBlocks.push({ lang, code })
    return `@@CODE_BLOCK_${idx}@@`
  })

  md = escapeHtml(md)

  md = md.replace(/^###\s*(.*)$/gm, '<h3>$1</h3>')
  md = md.replace(/^##\s*(.*)$/gm, '<h2>$1</h2>')
  md = md.replace(/^#\s*(.*)$/gm, '<h1>$1</h1>')

  md = md.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, rawUrl) => {
    const url = sanitizeUrl(rawUrl)
    if (!url) return text
    if (url.startsWith('/')) {
      const entityCard = renderEntityLinkCard(url, text)
      if (entityCard) return entityCard
      return `<a href="${escapeHtml(url)}" data-route="${escapeHtml(url)}" class="app-link">${text}</a>`
    }
    return `<a href="${escapeHtml(url)}">${text}</a>`
  })

  md = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  md = md.replace(/\*(.+?)\*/g, '<em>$1</em>')
  md = md.replace(/`([^`]+)`/g, '<code>$1</code>')

  md = md.replace(/(^|\n)((?:\d+\.\s+.+\n?)+)/g, (match) => {
    const items = match.trim().split(/\n/).filter(Boolean).map(line => line.replace(/^\d+\.\s+/, ''))
    return '\n<ol>' + items.map(item => `<li>${item}</li>`).join('') + '</ol>'
  })

  md = md.replace(/(^|\n)((?:[ \t]*[-*]\s+.+\n?)+)/g, (match) => {
    const items = match.trim().split(/\n/).filter(Boolean).map(line => line.replace(/^[ \t]*[-*]\s+/, ''))
    return '\n<ul>' + items.map(item => `<li>${item}</li>`).join('') + '</ul>'
  })

  const parts = md.split(/\n\s*\n/)
  md = parts.map(part => {
    const trimmed = part.trim()
    if (/^@@(CODE|MAP)_BLOCK_\d+@@$/.test(trimmed)) {
      return trimmed
    }
    const html = part.replace(/\n/g, '<br/>')
    return /^<(h\d|ul|ol|pre|blockquote|div)/.test(html) ? html : `<p>${html}</p>`
  }).join('\n')

  md = md.replace(/@@CODE_BLOCK_(\d+)@@/g, (match, idx) => {
    const block = codeBlocks[Number(idx)] || { lang: '', code: '' }
    const langLabel = block.lang ? `<div class="code-lang">${escapeHtml(block.lang)}</div>` : ''
    return `<pre>${langLabel}<code>${escapeHtml(block.code)}</code></pre>`
  })

  md = md.replace(/@@MAP_BLOCK_(\d+)@@/g, (match, idx) => {
    const props = mapBlocks[Number(idx)]
    return renderMapCard(props)
  })

  return md
}

const formatContent = (text) => {
  if (!text) return ''
  let cleaned = String(text)
  cleaned = cleaned.replace(/^正在思考.{0,3}/g, '')
  cleaned = cleaned.replace(/:{2,}map\{[^}]+\}/g, '')
  cleaned = cleaned.replace(/:{2,}map\{[^}]*$/g, '正在加载地图...')
  return renderMarkdown(cleaned.trim())
}

const mapWebRouteToApp = (route) => {
  if (!route || !route.startsWith('/')) return null

  if (route === '/' || route === '/home') return { type: 'tab', url: '/pages/index/index' }
  if (route === '/orders') return { type: 'tab', url: '/pages/order/list' }
  if (route === '/contents') return { type: 'tab', url: '/pages/content/list' }
  if (route === '/profile' || route === '/user') return { type: 'tab', url: '/pages/user/info' }
  if (route === '/ai') return { type: 'page', url: '/pages/ai/chat' }
  if (route === '/orders/create') return { type: 'page', url: '/pages/order/create' }
  if (route === '/contents/create') return { type: 'page', url: '/pages/content/create' }

  const orderMatch = route.match(/^\/orders\/(\d+)/)
  if (orderMatch) return { type: 'page', url: `/pages/order/detail?id=${orderMatch[1]}` }

  const contentMatch = route.match(/^\/contents\/(\d+)/)
  if (contentMatch) return { type: 'page', url: `/pages/content/detail?id=${contentMatch[1]}` }

  return null
}

const openExternalUrl = (url) => {
  // #ifdef H5
  if (typeof window !== 'undefined') {
    window.open(url, '_blank')
    return
  }
  // #endif

  uni.setClipboardData({
    data: url,
    success: () => showSuccess('链接已复制')
  })
}

const handleRichTextItemClick = (event) => {
  const node = event?.detail?.node || event?.detail || {}
  const attrs = node.attrs || node
  const href = attrs.href || attrs['data-route']
  if (!href) return

  const appRoute = mapWebRouteToApp(href)
  if (appRoute) {
    if (appRoute.type === 'tab') {
      uni.switchTab({ url: appRoute.url })
    } else {
      uni.navigateTo({ url: appRoute.url })
    }
    return
  }

  if (/^https?:\/\//.test(href)) {
    openExternalUrl(href)
  }
}

onLoad(async () => {
  inputText.value = uni.getStorageSync(DRAFT_KEY) || ''
  try {
    await loadConversations(true)
    startStreamStateSync()
  } catch (error) {
    showError(error.message || '加载 AI 会话失败')
  }
})

onShow(() => {
  syncStoredStreamMessage()
  startStreamStateSync()
})

const startStreamStateSync = () => {
  if (streamStateSyncTimer) return
  streamStateSyncTimer = setInterval(syncStoredStreamMessage, 600)
}

const stopStreamStateSync = () => {
  if (!streamStateSyncTimer) return
  clearInterval(streamStateSyncTimer)
  streamStateSyncTimer = null
}

const detachActiveStream = () => {
  activeStreamController = null
  stopStreamStateSync()
}

onUnload(detachActiveStream)
onUnmounted(detachActiveStream)
</script>

<style>
.chat-container {
  position: relative;
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f3f5f9;
  overflow: hidden;
}

.app-top {
  padding: 44rpx 30rpx 22rpx;
  background: #1f447a;
  color: #ffffff;
  flex-shrink: 0;
}

.back-button {
  position: absolute;
  left: 24rpx;
  top: 36rpx;
  z-index: 2;
  width: 58rpx;
  height: 58rpx;
  padding: 0;
  border: 1rpx solid rgba(255, 255, 255, 0.32);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.14);
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-button::after {
  border: none;
}

.back-chevron {
  width: 18rpx;
  height: 18rpx;
  border-left: 4rpx solid #ffffff;
  border-bottom: 4rpx solid #ffffff;
  transform: rotate(45deg);
  margin-left: 6rpx;
}

.title-row {
  padding-left: 76rpx;
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
}

.top-action {
  width: 128rpx;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  border: 1rpx solid rgba(255, 255, 255, 0.32);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  font-size: 24rpx;
}

.toolbar {
  display: flex;
  gap: 12rpx;
  margin-top: 24rpx;
}

.conversation-picker {
  flex: 1;
  min-width: 0;
}

.picker-view {
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  padding: 0 18rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.14);
}

.picker-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 24rpx;
  color: #ffffff;
}

.chevron {
  width: 12rpx;
  height: 12rpx;
  border-right: 3rpx solid rgba(255, 255, 255, 0.75);
  border-bottom: 3rpx solid rgba(255, 255, 255, 0.75);
  transform: rotate(45deg);
  flex: 0 0 12rpx;
}

.tool-btn {
  width: 96rpx;
  height: 64rpx;
  padding: 0;
  border: none;
  border-radius: 999rpx;
  font-size: 24rpx;
  line-height: 64rpx;
}

.tool-btn.subtle {
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}

.tool-btn.danger {
  background: #fff1f0;
  color: #b42318;
}

.tool-btn[disabled] {
  opacity: 0.55;
}

.messages-scroll {
  flex: 1;
  height: 0;
  padding: 26rpx 24rpx;
  box-sizing: border-box;
}

.message-item {
  margin-bottom: 28rpx;
  display: flex;
  justify-content: flex-start;
}

.message-item.user {
  justify-content: flex-end;
}

.user-bubble,
.assistant-bubble {
  max-width: 82%;
  padding: 20rpx 24rpx;
  border-radius: 14rpx;
  box-sizing: border-box;
}

.user-bubble {
  background: #1f447a;
  color: #ffffff;
  border-bottom-right-radius: 4rpx;
}

.user-message-text {
  color: #ffffff;
  font-size: 28rpx;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.assistant-row {
  max-width: 94%;
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
}

.assistant-avatar {
  width: 56rpx;
  height: 56rpx;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  font-weight: 800;
  flex: 0 0 56rpx;
}

.assistant-bubble {
  max-width: calc(100% - 70rpx);
  background: rgba(255, 255, 255, 0.94) !important;
  color: #263244;
  border: 1rpx solid rgba(214, 226, 240, 0.92) !important;
  border-bottom-left-radius: 4rpx;
  box-shadow: 0 8rpx 22rpx rgba(22, 34, 51, 0.06);
}

.operation-timeline {
  margin-bottom: 18rpx;
  padding: 16rpx 18rpx;
  border: 1rpx solid #e5ebf3;
  border-radius: 14rpx;
  background: #f8fafc;
}

.operation-overview {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 16rpx;
  padding: 18rpx;
  margin-bottom: 12rpx;
  border: 1rpx solid #dbeafe;
  border-radius: 14rpx;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fbff 100%);
}

.operation-overview.completed {
  border-color: #bbf7d0;
  background: linear-gradient(135deg, #ecfdf5 0%, #f8fffb 100%);
}

.operation-overview.pending {
  border-color: #fed7aa;
  background: linear-gradient(135deg, #fff7ed 0%, #fffaf5 100%);
}

.operation-overview.failed {
  border-color: #fecaca;
  background: linear-gradient(135deg, #fef2f2 0%, #fffafa 100%);
}

.operation-overview-main {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
}

.overview-status-dot {
  flex: 0 0 16rpx;
  width: 16rpx;
  height: 16rpx;
  margin-top: 10rpx;
  border-radius: 999rpx;
  background: #2563eb;
  box-shadow: 0 0 0 8rpx rgba(37, 99, 235, 0.12);
}

.overview-status-dot.completed {
  background: #16a34a;
  box-shadow: 0 0 0 8rpx rgba(22, 163, 74, 0.12);
}

.overview-status-dot.pending {
  background: #d97706;
  box-shadow: 0 0 0 8rpx rgba(217, 119, 6, 0.12);
}

.overview-status-dot.failed {
  background: #dc2626;
  box-shadow: 0 0 0 8rpx rgba(220, 38, 38, 0.12);
}

.overview-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.overview-kicker {
  color: #2563eb;
  font-size: 20rpx;
  font-weight: 900;
  line-height: 1.25;
}

.operation-overview.completed .overview-kicker {
  color: #15803d;
}

.operation-overview.pending .overview-kicker {
  color: #b45309;
}

.operation-overview.failed .overview-kicker {
  color: #b91c1c;
}

.overview-title {
  color: #172033;
  font-size: 25rpx;
  font-weight: 900;
  line-height: 1.35;
  word-break: break-word;
}

.overview-detail {
  color: #64748b;
  font-size: 21rpx;
  line-height: 1.45;
  word-break: break-word;
}

.overview-metrics {
  flex: 0 0 auto;
  max-width: 46%;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-content: flex-start;
  gap: 8rpx;
}

.overview-metric {
  min-width: 92rpx;
  padding: 8rpx 10rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.2);
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.72);
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.overview-metric-label {
  color: #64748b;
  font-size: 18rpx;
  font-weight: 800;
  line-height: 1.2;
}

.overview-metric-value {
  max-width: 150rpx;
  color: #172033;
  font-size: 20rpx;
  font-weight: 900;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.operation-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  padding: 0 0 12rpx;
  margin-bottom: 4rpx;
  border-bottom: 1rpx solid #edf2f7;
  color: #475569;
  font-size: 22rpx;
  font-weight: 900;
}

.operation-step {
  display: flex;
  gap: 14rpx;
  align-items: flex-start;
  padding: 10rpx 0;
}

.operation-step + .operation-step {
  border-top: 1rpx solid #edf1f6;
}

.operation-dot {
  width: 14rpx;
  height: 14rpx;
  margin-top: 10rpx;
  border-radius: 999rpx;
  background: #98a2b3;
  flex: 0 0 14rpx;
}

.operation-step.running .operation-dot {
  background: #1f447a;
  box-shadow: 0 0 0 7rpx rgba(31, 68, 122, 0.12);
}

.operation-step.completed .operation-dot {
  background: #16a34a;
}

.operation-step.failed .operation-dot {
  background: #dc2626;
}

.operation-step.pending .operation-dot {
  background: #d97706;
}

.operation-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.operation-title {
  color: #344054;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 1.45;
}

.operation-detail {
  color: #667085;
  font-size: 22rpx;
  line-height: 1.45;
  word-break: break-word;
}

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  margin-bottom: 18rpx;
}

.artifact-card {
  padding: 18rpx;
  border: 1rpx solid #dbe5f3;
  border-radius: 16rpx;
  background: #ffffff;
  box-shadow: 0 8rpx 22rpx rgba(22, 34, 51, 0.06);
}

.artifact-confirmation {
  border-color: #b8d4ff;
  background: #f8fbff;
}

.artifact-plan {
  border-color: #c7d2fe;
  background: #f5f7ff;
}

.artifact-plan .artifact-icon {
  background: #4f46e5;
}

.artifact-guide {
  border-color: #a7f3d0;
  background: #f0fdfa;
}

.artifact-guide .artifact-icon {
  background: #0f766e;
}

.artifact-weather {
  border-color: #b8d4ff;
  background: #eef6ff;
}

.artifact-weather .artifact-icon {
  background: #2563eb;
}

.artifact-order {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.artifact-order .artifact-icon {
  background: #16a34a;
}

.artifact-content {
  border-color: #ddd6fe;
  background: #f5f3ff;
}

.artifact-content .artifact-icon {
  background: #7c3aed;
}

.artifact-header {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
}

.artifact-icon {
  width: 42rpx;
  height: 42rpx;
  border-radius: 999rpx;
  background: #1f447a;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 900;
  flex: 0 0 42rpx;
}

.artifact-heading {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.artifact-title {
  color: #172033;
  font-size: 27rpx;
  font-weight: 900;
  line-height: 1.35;
}

.artifact-description {
  color: #667085;
  font-size: 23rpx;
  line-height: 1.45;
}

.artifact-highlights {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 14rpx;
}

.artifact-highlight {
  min-width: 136rpx;
  max-width: 100%;
  padding: 10rpx 12rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.22);
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.68);
  box-sizing: border-box;
}

.artifact-highlight text:first-child {
  display: block;
  color: #667085;
  font-size: 19rpx;
  font-weight: 800;
  line-height: 1.25;
}

.artifact-highlight-value {
  display: block;
  max-width: 220rpx;
  margin-top: 4rpx;
  overflow: hidden;
  color: #172033;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-result-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-top: 14rpx;
}

.artifact-result-item {
  width: 100%;
  min-height: 94rpx;
  padding: 14rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.24);
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.76);
  color: #172033;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  text-align: left;
  line-height: 1.35;
  box-shadow: none;
}

.artifact-result-item::after {
  border: none;
}

.artifact-result-item[disabled] {
  opacity: 0.72;
}

.artifact-result-item-hover {
  background: #edf4ff !important;
  border-color: #b6ccff !important;
}

.artifact-result-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.artifact-result-title-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.artifact-result-badge {
  flex: 0 0 auto;
  padding: 4rpx 8rpx;
  border-radius: 999rpx;
  background: rgba(31, 68, 122, 0.1);
  color: #1f447a;
  font-size: 18rpx;
  font-weight: 900;
  line-height: 1.2;
}

.artifact-result-title {
  min-width: 0;
  color: #172033;
  font-size: 24rpx;
  font-weight: 900;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-result-subtitle {
  color: #667085;
  font-size: 21rpx;
  line-height: 1.35;
  word-break: break-word;
}

.artifact-result-meta {
  max-width: 120rpx;
  color: #475467;
  font-size: 20rpx;
  font-weight: 800;
  line-height: 1.3;
  text-align: right;
}

.artifact-result-side {
  flex: 0 0 auto;
  max-width: 150rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6rpx;
}

.artifact-result-cta {
  min-width: 92rpx;
  padding: 7rpx 12rpx;
  border: 1rpx solid rgba(31, 68, 122, 0.18);
  border-radius: 999rpx;
  background: rgba(31, 68, 122, 0.1);
  color: #1f447a;
  font-size: 19rpx;
  font-weight: 900;
  line-height: 1.2;
  text-align: center;
}

.artifact-result-hint {
  color: #667085;
  font-size: 18rpx;
  font-weight: 700;
  line-height: 1.2;
  text-align: right;
}

.plan-step-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-top: 16rpx;
}

.plan-step {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  padding: 14rpx;
  border: 1rpx solid #e5e7eb;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.78);
}

.plan-step-index {
  width: 38rpx;
  height: 38rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 38rpx;
  background: #e0e7ff;
  color: #4338ca;
  font-size: 21rpx;
  font-weight: 900;
  line-height: 38rpx;
}

.plan-step.running .plan-step-index {
  background: #dbeafe;
  color: #2563eb;
  box-shadow: 0 0 0 6rpx rgba(37, 99, 235, 0.1);
}

.plan-step.completed .plan-step-index {
  background: #dcfce7;
  color: #15803d;
}

.plan-step.pending .plan-step-index {
  background: #fef3c7;
  color: #b45309;
}

.plan-step-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.plan-step-title {
  color: #172033;
  font-size: 24rpx;
  font-weight: 900;
  line-height: 1.35;
}

.plan-step-detail {
  color: #667085;
  font-size: 22rpx;
  line-height: 1.45;
  word-break: break-word;
}

.artifact-fields {
  margin-top: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.artifact-field {
  padding: 12rpx 14rpx;
  border-radius: 12rpx;
  border: 1rpx solid #edf1f6;
  background: #f8fafc;
}

.artifact-field.missing {
  border-color: #fed7aa;
  background: #fff7ed;
}

.artifact-field-label {
  display: block;
  color: #667085;
  font-size: 21rpx;
  line-height: 1.35;
}

.artifact-field-value {
  display: block;
  margin-top: 4rpx;
  color: #263244;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 1.4;
  word-break: break-word;
}

.artifact-actions {
  display: flex;
  gap: 10rpx;
  margin-top: 16rpx;
  flex-wrap: wrap;
}

.artifact-prompt-actions {
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(203, 213, 225, 0.76);
}

.guide-action-grid {
  display: flex;
  flex-direction: column;
}

.artifact-action {
  width: auto;
  min-width: 138rpx;
  height: 58rpx;
  padding: 0 18rpx;
  border: 1rpx solid #cfd8e6;
  border-radius: 999rpx;
  background: #ffffff;
  color: #344054;
  font-size: 24rpx;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  box-sizing: border-box;
}

.guide-action-card {
  width: 100%;
  min-height: 96rpx;
  height: auto;
  line-height: 1.3;
  padding: 16rpx 18rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6rpx;
  text-align: left;
  white-space: normal;
  background: rgba(248, 251, 255, 0.92);
  border-color: #bfdbfe;
  box-shadow: 0 8rpx 18rpx rgba(37, 99, 235, 0.08);
}

.guide-action-label {
  color: inherit;
  font-size: 24rpx;
  font-weight: 900;
  line-height: 1.35;
}

.guide-action-hint {
  color: #667085;
  font-size: 21rpx;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-word;
}

.artifact-action.primary {
  border-color: #1f447a;
  background: #1f447a;
  color: #ffffff;
}

.guide-action-card.primary .guide-action-hint {
  color: rgba(255, 255, 255, 0.78);
}

.artifact-action.ghost {
  color: #667085;
}

.artifact-action[disabled],
.artifact-action.disabled {
  opacity: 0.52;
  pointer-events: none;
}

.reply-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 16rpx;
}

.reply-action {
  margin: 0;
  min-height: 58rpx;
  line-height: 1.25;
  padding: 10rpx 16rpx;
  border: 1rpx solid #d9e7ff;
  border-radius: 999rpx;
  background: #f4f8ff;
  color: #1f447a;
  box-shadow: 0 8rpx 18rpx rgba(29, 78, 216, 0.08);
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  box-sizing: border-box;
}

.reply-action::after {
  border: none;
}

.reply-action[disabled] {
  opacity: 0.56;
}

.reply-action-hover {
  background: #eaf2ff !important;
  border-color: #b6ccff !important;
  box-shadow: 0 12rpx 24rpx rgba(29, 78, 216, 0.14);
}

.reply-action-icon {
  flex: 0 0 auto;
  width: 32rpx;
  height: 32rpx;
  line-height: 32rpx;
  border-radius: 999rpx;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 19rpx;
  font-weight: 900;
  text-align: center;
}

.reply-action-label {
  color: inherit;
  font-size: 22rpx;
  font-weight: 800;
  white-space: nowrap;
}

.artifact-editor {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 16rpx;
}

.artifact-edit-field {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.artifact-edit-input {
  width: 100%;
  min-height: 72rpx;
  padding: 14rpx 16rpx;
  border: 1rpx solid #cfd8e6;
  border-radius: 12rpx;
  box-sizing: border-box;
  background: #f8fafc;
  color: #172033;
  font-size: 25rpx;
  line-height: 1.45;
}

.artifact-edit-hint {
  padding: 12rpx 14rpx;
  border: 1rpx solid #fed7aa;
  border-radius: 12rpx;
  background: #fff7ed;
  color: #b45309;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.45;
}

.loading-dots {
  display: flex;
  gap: 8rpx;
  padding: 10rpx 0;
}

.loading-dots view {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: #8a94a6;
  animation: dot-pulse 1.4s ease-in-out infinite;
}

.loading-dots view:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots view:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-pulse {
  0%, 80%, 100% {
    transform: scale(0.65);
    opacity: 0.42;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.status-text {
  display: block;
  color: #8a94a6;
  font-size: 25rpx;
  line-height: 1.6;
}

.markdown-body {
  display: block;
  color: #263244;
  font-size: 28rpx;
  line-height: 1.7;
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 18rpx;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 24rpx 0 12rpx;
  color: #172033;
  font-weight: 800;
  line-height: 1.35;
}

.markdown-body :deep(h1) {
  font-size: 34rpx;
}

.markdown-body :deep(h2) {
  font-size: 31rpx;
}

.markdown-body :deep(h3) {
  font-size: 29rpx;
}

.markdown-body :deep(strong) {
  font-weight: 800;
}

.markdown-body :deep(em) {
  font-style: italic;
}

.markdown-body :deep(code) {
  padding: 3rpx 10rpx;
  border-radius: 6rpx;
  background: #eef1f5;
  color: #1f447a;
  font-family: monospace;
  font-size: 25rpx;
}

.markdown-body :deep(pre) {
  margin: 18rpx 0;
  padding: 20rpx;
  border-radius: 10rpx;
  background: #111827;
  color: #e5e7eb;
  overflow-x: auto;
  white-space: pre;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 24rpx;
}

.markdown-body :deep(.code-lang) {
  margin-bottom: 12rpx;
  color: #93c5fd;
  font-size: 22rpx;
  font-family: monospace;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 14rpx 0;
  padding-left: 36rpx;
}

.markdown-body :deep(li) {
  margin: 8rpx 0;
}

.markdown-body :deep(a),
.markdown-body :deep(.app-link) {
  color: #1f447a;
  text-decoration: none;
  font-weight: 700;
}

.markdown-body :deep(.entity-link-card) {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin: 16rpx 0;
  padding: 18rpx;
  border: 1rpx solid #e0e7ff;
  border-radius: 18rpx;
  background: #ffffff;
  box-shadow: 0 14rpx 34rpx rgba(23, 32, 51, 0.08);
  color: inherit;
  text-decoration: none;
}

.markdown-body :deep(.entity-icon) {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 68rpx;
  height: 68rpx;
  border-radius: 18rpx;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 900;
}

.markdown-body :deep(.entity-order .entity-icon) {
  background: #1f447a;
}

.markdown-body :deep(.entity-content .entity-icon) {
  background: #078669;
}

.markdown-body :deep(.entity-main) {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.markdown-body :deep(.entity-title) {
  color: #172033;
  font-size: 27rpx;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.markdown-body :deep(.entity-subtitle) {
  color: #667085;
  font-size: 22rpx;
}

.markdown-body :deep(.entity-action) {
  flex: 0 0 auto;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 900;
}

.markdown-body :deep(.entity-content .entity-action) {
  color: #078669;
}

.markdown-body :deep(.map-card) {
  margin: 18rpx 0;
  overflow: hidden;
  border: 1rpx solid #d9e7ff;
  border-radius: 20rpx;
  background: #ffffff;
  box-shadow: 0 16rpx 38rpx rgba(29, 78, 216, 0.10);
}

.markdown-body :deep(.map-tile-stage) {
  position: relative;
  height: 330rpx;
  overflow: hidden;
  background: #e0ecf8;
}

.markdown-body :deep(.map-tile-grid) {
  position: absolute;
  display: grid;
  grid-template-columns: repeat(3, 256px);
  grid-template-rows: repeat(3, 256px);
  width: 768px;
  height: 768px;
}

.markdown-body :deep(.map-tile) {
  display: block;
  width: 256px;
  height: 256px;
}

.markdown-body :deep(.map-pin) {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 42rpx;
  height: 42rpx;
  z-index: 2;
  transform: translate(-50%, -100%) rotate(-45deg);
  border-radius: 50% 50% 50% 0;
  background: #ef4444;
  box-shadow: 0 8rpx 18rpx rgba(127, 29, 29, 0.35);
}

.markdown-body :deep(.map-pin-dot) {
  position: absolute;
  left: 11rpx;
  top: 11rpx;
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  background: #ffffff;
}

.markdown-body :deep(.map-badge) {
  position: absolute;
  left: 18rpx;
  top: 18rpx;
  z-index: 2;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.93);
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 800;
  box-shadow: 0 10rpx 26rpx rgba(23, 32, 51, 0.12);
}

.markdown-body :deep(.map-card-meta) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 18rpx;
}

.markdown-body :deep(.map-card-info) {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.markdown-body :deep(.map-card-title) {
  color: #172033;
  font-size: 27rpx;
}

.markdown-body :deep(.map-card-coords) {
  color: #667085;
  font-size: 21rpx;
  font-family: monospace;
}

.markdown-body :deep(.map-card-action) {
  flex: 0 0 auto;
  padding: 11rpx 16rpx;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 800;
  text-decoration: none;
}

.inline-map-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  margin-top: 12rpx;
}

.inline-map-card {
  overflow: hidden;
  border: 1rpx solid #d9e7ff;
  border-radius: 20rpx;
  background: #ffffff;
  box-shadow: 0 16rpx 38rpx rgba(29, 78, 216, 0.10);
}

.inline-map-stage {
  position: relative;
  height: 330rpx;
  overflow: hidden;
  background: #e0ecf8;
  cursor: grab;
}

.inline-map-grid {
  position: absolute;
  display: grid;
  grid-template-columns: repeat(3, 256px);
  grid-template-rows: repeat(3, 256px);
  width: 768px;
  height: 768px;
}

.inline-map-tile {
  display: block;
  width: 256px;
  height: 256px;
}

.inline-map-pin {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 42rpx;
  height: 42rpx;
  z-index: 2;
  transform: translate(-50%, -100%) rotate(-45deg);
  border-radius: 50% 50% 50% 0;
  background: #ef4444;
  box-shadow: 0 8rpx 18rpx rgba(127, 29, 29, 0.35);
}

.inline-map-pin-dot {
  position: absolute;
  left: 11rpx;
  top: 11rpx;
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  background: #ffffff;
}

.inline-map-badge {
  position: absolute;
  left: 18rpx;
  top: 18rpx;
  z-index: 2;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.93);
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 800;
  box-shadow: 0 10rpx 26rpx rgba(23, 32, 51, 0.12);
}

.inline-map-controls {
  position: absolute;
  right: 18rpx;
  top: 18rpx;
  z-index: 3;
  display: grid;
  grid-template-columns: repeat(2, 56rpx);
  gap: 8rpx;
}

.inline-map-control {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  padding: 0;
  border: 1rpx solid rgba(148, 163, 184, 0.35);
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.92);
  color: #1f2937;
  font-size: 26rpx;
  font-weight: 900;
  box-shadow: 0 8rpx 18rpx rgba(15, 23, 42, 0.12);
}

.inline-map-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 18rpx;
}

.inline-map-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5rpx;
}

.inline-map-title {
  color: #172033;
  font-size: 27rpx;
  font-weight: 900;
  line-height: 1.35;
}

.inline-map-coords {
  color: #667085;
  font-size: 21rpx;
  font-family: monospace;
}

.inline-map-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10rpx;
}

.inline-map-open {
  flex: 0 0 auto;
  height: 58rpx;
  line-height: 58rpx;
  margin: 0;
  padding: 0 16rpx;
  border: none;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 800;
  box-sizing: border-box;
  white-space: nowrap;
}

.inline-map-order {
  min-width: 154rpx;
  background: #1f447a;
  color: #ffffff;
  box-shadow: 0 10rpx 24rpx rgba(31, 68, 122, 0.22);
}

.inline-map-open[disabled] {
  opacity: 0.58;
  box-shadow: none;
}

.inline-map-control::after,
.inline-map-open::after {
  border: none;
}

.tool-btn-hover,
.inline-map-control-hover,
.memory-icon-btn-hover,
.memory-retry-hover {
  background: rgba(31, 68, 122, 0.12) !important;
  border-color: rgba(31, 68, 122, 0.2) !important;
}

.inline-map-open-hover {
  background: #dbeafe !important;
  border-color: #b6ccff !important;
  color: #1f447a !important;
}

.inline-map-order-hover {
  background: #183760 !important;
  border-color: #1f447a !important;
  color: #ffffff !important;
}

.tool-btn-danger-hover,
.memory-delete-hover {
  background: rgba(180, 35, 24, 0.14) !important;
  border-color: rgba(180, 35, 24, 0.18) !important;
}

.inline-map-hint {
  display: block;
  padding: 0 18rpx 18rpx;
  color: #667085;
  font-size: 22rpx;
  line-height: 1.45;
}

.empty-state {
  min-height: 560rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  text-align: center;
  color: #8a94a6;
}

.empty-logo {
  width: 108rpx;
  height: 108rpx;
  border-radius: 28rpx;
  background: #edf4ff;
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34rpx;
  font-weight: 800;
}

.empty-title {
  color: #172033;
  font-size: 34rpx;
  font-weight: 800;
}

.empty-subtitle {
  max-width: 520rpx;
  color: #8a94a6;
  font-size: 26rpx;
  line-height: 1.55;
}

.starter-grid {
  width: 100%;
  max-width: 650rpx;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
  margin-top: 18rpx;
}

.starter-card {
  min-height: 132rpx;
  padding: 18rpx;
  border: 1rpx solid #d9e7ff;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.92);
  color: #172033;
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  text-align: left;
  line-height: 1.35;
  box-shadow: 0 14rpx 32rpx rgba(29, 78, 216, 0.08);
  transition: background 0.16s, border-color 0.16s, transform 0.16s, box-shadow 0.16s;
}

.starter-card::after {
  border: none;
}

.starter-card[disabled] {
  opacity: 0.58;
}

.starter-card-hover {
  background: #edf4ff !important;
  border-color: #b6ccff !important;
  transform: translateY(-2rpx);
  box-shadow: 0 18rpx 38rpx rgba(29, 78, 216, 0.14);
}

.starter-icon {
  width: 46rpx;
  height: 46rpx;
  flex: 0 0 46rpx;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 23rpx;
  font-weight: 800;
}

.starter-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.starter-title {
  color: #172033;
  font-size: 25rpx;
  font-weight: 800;
}

.starter-detail {
  color: #667085;
  font-size: 22rpx;
  line-height: 1.38;
}

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 16rpx;
  padding: 18rpx 24rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #ffffff;
  border-top: 1rpx solid #e8edf5;
  box-shadow: 0 -8rpx 22rpx rgba(22, 34, 51, 0.05);
}

.input {
  flex: 1;
  min-height: 72rpx;
  max-height: 220rpx;
  padding: 18rpx 22rpx;
  border: 1rpx solid #d9e0ea;
  border-radius: 18rpx;
  box-sizing: border-box;
  font-size: 27rpx;
  line-height: 1.45;
  background: #f8fafc;
  color: #172033;
}

.send-btn {
  width: 126rpx;
  height: 72rpx;
  line-height: 72rpx;
  background: #1f447a;
  color: #ffffff;
  border-radius: 999rpx;
  font-size: 27rpx;
  border: none;
  padding: 0;
}

.send-btn[disabled] {
  background: #c8d0dc;
}

.memory-mask {
  position: absolute;
  inset: 0;
  z-index: 40;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(4rpx);
}

.memory-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 41;
  width: 680rpx;
  max-width: 92vw;
  background: rgba(248, 251, 255, 0.96);
  border-left: 1rpx solid rgba(148, 163, 184, 0.22);
  box-shadow: -18rpx 0 48rpx rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.memory-header {
  min-height: 112rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 20rpx 28rpx;
  border-bottom: 1rpx solid rgba(226, 232, 240, 0.9);
}

.memory-heading {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.memory-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #172033;
  line-height: 1.25;
}

.memory-subtitle {
  color: #667085;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.35;
}

.memory-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.memory-icon-btn {
  height: 56rpx;
  min-width: 84rpx;
  padding: 0 18rpx;
  border: 1rpx solid #dbeafe;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 54rpx;
}

.memory-icon-btn.ghost {
  background: #ffffff;
  color: #475467;
  border-color: #e2e8f0;
}

.memory-icon-btn[disabled] {
  opacity: 0.62;
}

.memory-icon-btn::after,
.memory-retry::after,
.memory-delete::after {
  border: none;
}

.memory-list {
  flex: 1;
  height: 0;
  padding: 20rpx 24rpx 28rpx;
  box-sizing: border-box;
}

.memory-state,
.memory-empty {
  border: 1rpx dashed rgba(148, 163, 184, 0.42);
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.78);
  color: #667085;
}

.memory-state {
  display: flex;
  align-items: center;
  gap: 18rpx;
  padding: 24rpx;
}

.memory-state.error {
  border-color: rgba(248, 113, 113, 0.45);
  background: rgba(254, 242, 242, 0.82);
}

.memory-spinner,
.memory-state-icon,
.memory-empty-icon {
  flex: 0 0 auto;
  width: 56rpx;
  height: 56rpx;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.memory-spinner {
  border: 5rpx solid #dbeafe;
  border-top-color: #3768d8;
  animation: memory-spin 0.85s linear infinite;
}

.memory-state-icon,
.memory-empty-icon {
  background: #edf4ff;
  color: #1f447a;
  font-size: 26rpx;
  font-weight: 900;
}

.memory-state-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.memory-state-title,
.memory-empty-title {
  color: #172033;
  font-size: 26rpx;
  font-weight: 900;
  line-height: 1.35;
}

.memory-state-text,
.memory-empty-text {
  color: #667085;
  font-size: 22rpx;
  line-height: 1.5;
}

.memory-retry {
  flex: 0 0 auto;
  height: 52rpx;
  padding: 0 18rpx;
  border: 1rpx solid #bfdbfe;
  border-radius: 14rpx;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 50rpx;
}

.memory-empty {
  min-height: 280rpx;
  padding: 48rpx 24rpx;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12rpx;
}

.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx;
  margin-bottom: 14rpx;
  border: 1rpx solid rgba(226, 232, 240, 0.96);
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 10rpx 22rpx rgba(15, 23, 42, 0.05);
}

.memory-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.memory-tag {
  align-self: flex-start;
  max-width: 100%;
  padding: 5rpx 14rpx;
  border-radius: 999rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 21rpx;
  font-weight: 900;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-content {
  font-size: 26rpx;
  color: #344054;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.memory-delete {
  width: 96rpx;
  height: 52rpx;
  border: 1rpx solid transparent;
  border-radius: 14rpx;
  background: #fff1f0;
  color: #b42318;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 50rpx;
  padding: 0;
}

.memory-delete[disabled] {
  opacity: 0.55;
}

@keyframes memory-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media screen and (min-width: 768px) {
  .memory-panel {
    width: 420px;
    max-width: 42vw;
  }
}

@media screen and (max-width: 520px) {
  .operation-overview {
    flex-direction: column;
  }

  .overview-metrics {
    max-width: none;
    justify-content: flex-start;
  }

  .overview-metric-value {
    max-width: 210rpx;
  }

  .inline-map-meta {
    align-items: stretch;
    flex-direction: column;
  }

  .inline-map-actions {
    width: 100%;
    justify-content: stretch;
  }

  .inline-map-actions .inline-map-open {
    flex: 1 1 0;
    min-width: 0;
  }
}

@media (hover: hover) {
  .tool-btn.subtle:hover,
  .top-action:hover,
  .picker-view:hover,
  .artifact-action:hover,
  .artifact-result-item:hover,
  .reply-action:hover,
  .starter-card:hover,
  .inline-map-control:hover,
  .inline-map-open:hover,
  .memory-icon-btn:hover,
  .memory-retry:hover {
    background: rgba(31, 68, 122, 0.12);
  }

  .tool-btn.danger:hover,
  .memory-delete:hover {
    background: rgba(180, 35, 24, 0.14);
  }
}

@media (prefers-color-scheme: dark) {
  .chat-container {
    background: #101722;
  }

  .app-top {
    background: #0b1320;
    border-bottom: 1rpx solid rgba(148, 163, 184, 0.18);
  }

  .back-button,
  .top-action,
  .picker-view,
  .tool-btn.subtle {
    background: rgba(148, 163, 184, 0.12);
    border-color: rgba(148, 163, 184, 0.22);
    color: #edf4ff;
  }

  .tool-btn.danger,
  .memory-delete {
    background: rgba(239, 68, 68, 0.12);
    color: #fca5a5;
  }

  .assistant-avatar {
    background: #162235;
    color: #9ab8ff;
  }

  .assistant-bubble,
  .operation-timeline,
  .artifact-card,
  .starter-card,
  .inline-map-card,
  .memory-panel {
    background: #172235 !important;
    color: #edf4ff !important;
    border-color: rgba(148, 163, 184, 0.22) !important;
    box-shadow: 0 16rpx 34rpx rgba(0, 0, 0, 0.22) !important;
  }

  .artifact-confirmation {
    background: #132033;
    border-color: rgba(91, 140, 255, 0.34);
  }

  .artifact-plan {
    background: #191f3a;
    border-color: rgba(129, 140, 248, 0.32);
  }

  .artifact-plan .artifact-icon {
    background: #4f46e5;
    color: #e0e7ff;
  }

  .operation-overview {
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.18) 0%, rgba(23, 34, 53, 0.96) 100%);
    border-color: rgba(96, 165, 250, 0.28);
  }

  .operation-overview.completed {
    background: linear-gradient(135deg, rgba(22, 163, 74, 0.16) 0%, rgba(23, 34, 53, 0.96) 100%);
    border-color: rgba(74, 222, 128, 0.24);
  }

  .operation-overview.pending {
    background: linear-gradient(135deg, rgba(217, 119, 6, 0.16) 0%, rgba(23, 34, 53, 0.96) 100%);
    border-color: rgba(251, 191, 36, 0.26);
  }

  .operation-overview.failed {
    background: linear-gradient(135deg, rgba(220, 38, 38, 0.16) 0%, rgba(23, 34, 53, 0.96) 100%);
    border-color: rgba(248, 113, 113, 0.26);
  }

  .overview-kicker {
    color: #93c5fd;
  }

  .operation-overview.completed .overview-kicker {
    color: #86efac;
  }

  .operation-overview.pending .overview-kicker {
    color: #fbbf24;
  }

  .operation-overview.failed .overview-kicker {
    color: #fca5a5;
  }

  .operation-title,
  .overview-title,
  .overview-metric-value,
  .artifact-title,
  .artifact-field-value,
  .plan-step-title,
  .markdown-body,
  .markdown-body :deep(h1),
  .markdown-body :deep(h2),
  .markdown-body :deep(h3),
  .markdown-body :deep(.entity-title),
  .markdown-body :deep(.map-card-title),
  .inline-map-title,
  .memory-title,
  .memory-content,
  .starter-title,
  .empty-title {
    color: #edf4ff;
  }

  .operation-detail,
  .overview-detail,
  .overview-metric-label,
  .operation-summary-head,
  .artifact-description,
  .artifact-field-label,
  .artifact-highlight text:first-child,
  .plan-step-detail,
  .markdown-body :deep(.entity-subtitle),
  .markdown-body :deep(.map-card-coords),
  .inline-map-coords,
  .inline-map-hint,
  .memory-empty,
  .starter-detail,
  .empty-subtitle,
  .status-text {
    color: #94a3b8;
  }

  .starter-card-hover,
  .starter-card:hover {
    background: #1f2d44 !important;
    border-color: rgba(148, 163, 184, 0.32) !important;
    box-shadow: 0 18rpx 38rpx rgba(0, 0, 0, 0.24);
  }

  .starter-icon {
    background: #223554;
    color: #bfdbfe;
  }

  .operation-step + .operation-step,
  .operation-summary-head,
  .memory-header,
  .memory-item {
    border-color: rgba(148, 163, 184, 0.16);
  }

  .overview-metric {
    background: rgba(15, 23, 42, 0.46);
    border-color: rgba(148, 163, 184, 0.18);
  }

  .artifact-field,
  .artifact-highlight,
  .artifact-result-item,
  .plan-step,
  .artifact-edit-input,
  .input {
    background: #101a2a;
    border-color: rgba(148, 163, 184, 0.22);
    color: #edf4ff;
  }

  .artifact-field.missing {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.35);
  }

  .artifact-edit-hint {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.35);
    color: #fbbf24;
  }

  .artifact-highlight-value {
    color: #edf4ff;
  }

  .artifact-result-item-hover,
  .artifact-result-item:hover {
    background: #1f2d44 !important;
    border-color: rgba(154, 184, 255, 0.38) !important;
  }

  .artifact-result-title {
    color: #edf4ff;
  }

  .artifact-result-subtitle,
  .artifact-result-meta,
  .artifact-result-hint {
    color: #94a3b8;
  }

  .artifact-result-badge {
    background: #223554;
    color: #bfdbfe;
  }

  .artifact-result-cta {
    background: rgba(96, 165, 250, 0.16);
    border-color: rgba(147, 197, 253, 0.3);
    color: #bfdbfe;
  }

  .plan-step-index {
    background: rgba(129, 140, 248, 0.18);
    color: #c7d2fe;
  }

  .plan-step.running .plan-step-index {
    background: rgba(96, 165, 250, 0.2);
    color: #bfdbfe;
  }

  .plan-step.completed .plan-step-index {
    background: rgba(34, 197, 94, 0.18);
    color: #bbf7d0;
  }

  .plan-step.pending .plan-step-index {
    background: rgba(245, 158, 11, 0.18);
    color: #fde68a;
  }

  .artifact-action,
  .reply-action,
  .inline-map-control,
  .inline-map-open,
  .memory-icon-btn,
  .memory-retry,
  .markdown-body :deep(.map-card-action),
  .markdown-body :deep(.entity-link-card) {
    background: #101a2a;
    border-color: rgba(148, 163, 184, 0.24);
    color: #dbe7f8;
  }

  .memory-icon-btn.ghost {
    background: #101a2a;
    border-color: rgba(148, 163, 184, 0.24);
    color: #dbe7f8;
  }

  .artifact-action.primary,
  .inline-map-order,
  .send-btn {
    background: #3768d8;
    border-color: #5b8cff;
    color: #ffffff;
  }

  .artifact-action.ghost {
    color: #94a3b8;
  }

  .reply-action-icon {
    background: rgba(96, 165, 250, 0.18);
    color: #bfdbfe;
  }

  .reply-action-hover,
  .reply-action:hover {
    background: #1f2d44 !important;
    border-color: rgba(154, 184, 255, 0.38) !important;
    box-shadow: 0 12rpx 26rpx rgba(0, 0, 0, 0.24);
  }

  .tool-btn-hover,
  .inline-map-control-hover,
  .inline-map-control:hover,
  .inline-map-open-hover,
  .inline-map-open:hover,
  .memory-icon-btn-hover,
  .memory-icon-btn:hover,
  .memory-retry:hover {
    background: #1f2d44 !important;
    border-color: rgba(154, 184, 255, 0.38) !important;
    color: #edf4ff !important;
    box-shadow: 0 12rpx 26rpx rgba(0, 0, 0, 0.24);
  }

  .inline-map-order-hover,
  .inline-map-order:hover,
  .artifact-action.primary:hover {
    background: #4f7ff0 !important;
    border-color: #7aa2ff !important;
    color: #ffffff !important;
    box-shadow: 0 14rpx 30rpx rgba(37, 99, 235, 0.28);
  }

  .tool-btn-danger-hover,
  .tool-btn.danger:hover,
  .memory-delete-hover,
  .memory-delete:hover {
    background: rgba(248, 113, 113, 0.18) !important;
    border-color: rgba(248, 113, 113, 0.28) !important;
    color: #fecaca !important;
  }

  .markdown-body :deep(code) {
    background: #101a2a;
    color: #bfdbfe;
  }

  .markdown-body :deep(.entity-link-card),
  .markdown-body :deep(.map-card) {
    background: #172235;
    border-color: rgba(148, 163, 184, 0.22);
    box-shadow: 0 16rpx 34rpx rgba(0, 0, 0, 0.22);
  }

  .markdown-body :deep(.map-badge),
  .inline-map-badge {
    background: rgba(15, 23, 42, 0.86);
    color: #bfdbfe;
  }

  .input-bar {
    background: #0f1726;
    border-top-color: rgba(148, 163, 184, 0.18);
  }

  .memory-mask {
    background: rgba(0, 0, 0, 0.56);
  }

  .memory-subtitle,
  .memory-state-text,
  .memory-empty-text {
    color: #94a3b8;
  }

  .memory-state,
  .memory-empty,
  .memory-item {
    background: #101a2a;
    border-color: rgba(148, 163, 184, 0.22);
    box-shadow: 0 12rpx 26rpx rgba(0, 0, 0, 0.2);
  }

  .memory-state.error {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(248, 113, 113, 0.28);
  }

  .memory-state-title,
  .memory-empty-title {
    color: #edf4ff;
  }

  .memory-state-icon,
  .memory-empty-icon {
    background: #223554;
    color: #bfdbfe;
  }

  .memory-spinner {
    border-color: rgba(96, 165, 250, 0.2);
    border-top-color: #93c5fd;
  }

  .memory-tag {
    background: #223554;
    color: #bfdbfe;
  }
}
</style>
