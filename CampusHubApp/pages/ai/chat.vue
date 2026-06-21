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
        <button class="tool-btn subtle" @click="openMemoryPanel">记忆</button>
        <button class="tool-btn danger" :disabled="!currentCid" @click="deleteCurrentConversation">删除</button>
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
                  <view class="artifact-icon">{{ artifact.type === 'confirmation' ? '!' : 'i' }}</view>
                  <view class="artifact-heading">
                    <text class="artifact-title">{{ artifact.title || '结果卡片' }}</text>
                    <text v-if="artifact.description" class="artifact-description">{{ artifact.description }}</text>
                  </view>
                </view>
                <view v-if="artifact.fields && artifact.fields.length && !artifact.editing" class="artifact-fields">
                  <view
                    v-for="(field, fieldIndex) in artifact.fields"
                    :key="fieldIndex"
                    class="artifact-field"
                    :class="{ missing: field.missing }"
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
                      :placeholder="field.missing ? '补充这个信息' : '修改内容'"
                    />
                  </view>
                </view>
                <view v-if="artifact.type === 'confirmation'" class="artifact-actions">
                  <template v-if="artifact.editing">
                    <button class="artifact-action primary" :disabled="loading" @click="handleArtifactAction(artifact, 'confirm-edited')">保存并确认</button>
                    <button class="artifact-action ghost" :disabled="loading" @click="handleArtifactAction(artifact, 'cancel-edit')">退出编辑</button>
                  </template>
                  <template v-else>
                    <button class="artifact-action primary" :disabled="loading" @click="handleArtifactAction(artifact, 'confirm')">确认执行</button>
                    <button class="artifact-action" :disabled="loading" @click="handleArtifactAction(artifact, 'edit')">修改草稿</button>
                    <button class="artifact-action ghost" :disabled="loading" @click="handleArtifactAction(artifact, 'cancel')">取消</button>
                  </template>
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
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'zoom-in')">+</button>
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'zoom-out')">-</button>
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'north')">↑</button>
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'south')">↓</button>
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'west')">←</button>
                    <button class="inline-map-control" @click.stop="adjustMapCard(mapCard, 'east')">→</button>
                  </view>
                </view>
                <view class="inline-map-meta">
                  <view class="inline-map-info">
                    <text class="inline-map-title">{{ mapCard.title }}</text>
                    <text class="inline-map-coords">{{ mapCard.lng.toFixed(6) }}, {{ mapCard.lat.toFixed(6) }} · zoom {{ mapCard.zoom }}</text>
                  </view>
                  <button class="inline-map-open" @click="openExternalUrl(mapCard.link)">打开高德地图</button>
                </view>
                <text class="inline-map-hint">可拖拽地图，也可以使用缩放和平移按钮。</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <view v-if="messages.length === 0" class="empty-state">
        <view class="empty-logo">AI</view>
        <text class="empty-title">CampusHub AI 助手</text>
        <text class="empty-subtitle">可以帮你搜索约伴活动、整理校园信息，Markdown 回复会自动排版。</text>
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
        <text class="memory-title">AI 记忆</text>
        <button class="memory-close" @click="closeMemoryPanel">关闭</button>
      </view>
      <scroll-view class="memory-list" scroll-y>
        <view v-if="memoryLoading" class="memory-empty">加载中...</view>
        <view v-else-if="memories.length === 0" class="memory-empty">AI 还没有记住关于你的任何信息</view>
        <view v-for="mem in memories" :key="mem.memId || mem.id" class="memory-item">
          <view class="memory-main">
            <text class="memory-tag">{{ mem.category || '偏好' }}</text>
            <text class="memory-content">{{ mem.content }}</text>
          </view>
          <button class="memory-delete" @click="deleteMemory(mem)">删除</button>
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
const showMemoryPanel = ref(false)
const scrollTop = ref(0)
const mapStates = ref({})

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
    state: payload.state || (eventName === 'confirm_required' ? 'pending' : 'running')
  }
}

const normalizeArtifact = (eventName, data) => {
  const payload = parseAgentEventData(data)
  const type = payload.type || (eventName === 'confirm_required' ? 'confirmation' : 'generic')
  const fields = Array.isArray(payload.fields) ? payload.fields : []
  return {
    ...payload,
    type,
    fields: fields.map(field => {
      const normalized = field && typeof field === 'object' ? field : { label: '信息', value: field }
      const displayValue = formatArtifactValue(normalized.value)
      return {
        ...normalized,
        editValue: displayValue === '未填写' ? '' : displayValue
      }
    }),
    editing: false
  }
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

const loadConversations = async (selectFirst = false) => {
  if (!ensureLogin()) return

  const list = await aiApi.listConversations()
  conversations.value = normalizeList(list)

  const currentExists = conversations.value.some(item => item.cid === currentCid.value)
  if (currentCid.value && currentExists) {
    await loadMessages(currentCid.value)
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

const handleArtifactAction = (artifact, action) => {
  const title = artifact?.title || '这个草稿'
  if (action === 'edit') {
    artifact.editing = true
    artifact.fields = (artifact.fields || []).map(field => ({
      ...field,
      editValue: field.editValue ?? (formatArtifactValue(field.value) === '未填写' ? '' : formatArtifactValue(field.value))
    }))
    return
  }
  if (action === 'cancel-edit') {
    artifact.editing = false
    return
  }
  const messages = {
    confirm: artifact?.confirmMessage || `我确认执行这个草稿：${title}`,
    'confirm-edited': buildEditedArtifactMessage(artifact),
    cancel: artifact?.cancelMessage || `取消这个草稿：${title}`
  }
  sendMessageText(messages[action])
}

const buildEditedArtifactMessage = (artifact) => {
  const title = artifact?.title || '这个草稿'
  const fields = (artifact?.fields || [])
    .map(field => {
      const value = String(field.editValue ?? '').trim()
      return value ? `${field.label}: ${value}` : ''
    })
    .filter(Boolean)
  const fieldText = fields.length ? `\n${fields.join('\n')}` : ''
  return `我确认按修改后的内容执行这个草稿：${title}${fieldText}`
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

    await loadConversations(false)
    await switchConversation(sentCid)
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
  try {
    const list = await aiApi.getMemories()
    memories.value = normalizeList(list)
  } catch (error) {
    showError(error.message || '加载记忆失败')
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
  if (!memoryId) return

  uni.showModal({
    title: '删除记忆',
    content: '确定删除这条 AI 记忆吗？',
    success: async (res) => {
      if (!res.confirm) return

      try {
        await aiApi.deleteMemory(memoryId)
        memories.value = memories.value.filter(item => (item.memId || item.id) !== memoryId)
        showSuccess('已删除')
      } catch (error) {
        showError(error.message || '删除失败')
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
  background: #ffffff;
  color: #263244;
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

.artifact-action {
  width: auto;
  min-width: 138rpx;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0 18rpx;
  border: 1rpx solid #cfd8e6;
  border-radius: 999rpx;
  background: #ffffff;
  color: #344054;
  font-size: 24rpx;
  font-weight: 800;
}

.artifact-action.primary {
  border-color: #1f447a;
  background: #1f447a;
  color: #ffffff;
}

.artifact-action.ghost {
  color: #667085;
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

.inline-map-open {
  flex: 0 0 auto;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0 16rpx;
  border: none;
  border-radius: 14rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 800;
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
  z-index: 10;
  background: rgba(0, 0, 0, 0.35);
}

.memory-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 11;
  width: 620rpx;
  max-width: 86%;
  background: #ffffff;
  box-shadow: -8rpx 0 24rpx rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
}

.memory-header {
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28rpx;
  border-bottom: 1rpx solid #e8edf5;
}

.memory-title {
  font-size: 32rpx;
  font-weight: 800;
  color: #172033;
}

.memory-close {
  height: 56rpx;
  padding: 0 20rpx;
  border: none;
  border-radius: 999rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 24rpx;
  line-height: 56rpx;
}

.memory-list {
  flex: 1;
  height: 0;
  padding: 12rpx 24rpx;
  box-sizing: border-box;
}

.memory-empty {
  padding: 80rpx 20rpx;
  text-align: center;
  color: #8a94a6;
  font-size: 26rpx;
}

.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 24rpx 0;
  border-bottom: 1rpx solid #edf1f6;
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
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
}

.memory-content {
  font-size: 26rpx;
  color: #344054;
  line-height: 1.5;
  word-break: break-word;
}

.memory-delete {
  width: 96rpx;
  height: 52rpx;
  border: none;
  border-radius: 999rpx;
  background: #fff1f0;
  color: #b42318;
  font-size: 24rpx;
  line-height: 52rpx;
  padding: 0;
}

@media (hover: hover) {
  .tool-btn.subtle:hover,
  .top-action:hover,
  .picker-view:hover,
  .artifact-action:hover,
  .inline-map-control:hover,
  .inline-map-open:hover,
  .memory-close:hover {
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
  .inline-map-card,
  .memory-panel {
    background: #172235;
    color: #edf4ff;
    border-color: rgba(148, 163, 184, 0.22);
    box-shadow: 0 16rpx 34rpx rgba(0, 0, 0, 0.22);
  }

  .artifact-confirmation {
    background: #132033;
    border-color: rgba(91, 140, 255, 0.34);
  }

  .operation-title,
  .artifact-title,
  .artifact-field-value,
  .markdown-body,
  .markdown-body :deep(h1),
  .markdown-body :deep(h2),
  .markdown-body :deep(h3),
  .markdown-body :deep(.entity-title),
  .markdown-body :deep(.map-card-title),
  .inline-map-title,
  .memory-title,
  .memory-content,
  .empty-title {
    color: #edf4ff;
  }

  .operation-detail,
  .artifact-description,
  .artifact-field-label,
  .markdown-body :deep(.entity-subtitle),
  .markdown-body :deep(.map-card-coords),
  .inline-map-coords,
  .inline-map-hint,
  .memory-empty,
  .empty-subtitle,
  .status-text {
    color: #94a3b8;
  }

  .operation-step + .operation-step,
  .memory-header,
  .memory-item {
    border-color: rgba(148, 163, 184, 0.16);
  }

  .artifact-field,
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

  .artifact-action,
  .inline-map-control,
  .inline-map-open,
  .memory-close,
  .markdown-body :deep(.map-card-action),
  .markdown-body :deep(.entity-link-card) {
    background: #101a2a;
    border-color: rgba(148, 163, 184, 0.24);
    color: #dbe7f8;
  }

  .artifact-action.primary,
  .send-btn {
    background: #3768d8;
    border-color: #5b8cff;
    color: #ffffff;
  }

  .artifact-action.ghost {
    color: #94a3b8;
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

  .memory-tag {
    background: #223554;
    color: #bfdbfe;
  }
}
</style>
