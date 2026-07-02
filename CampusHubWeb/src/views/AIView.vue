<template>
  <div class="ai-view">
    <div class="ai-layout">
      <!-- 左侧：会话列表 -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <button class="btn-new-chat" @click="handleNewConversation" title="新建对话">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
            新建对话
          </button>
        </div>
        <div class="conversation-list">
          <div
            v-for="conv in conversations"
            :key="conv.cid"
            :class="['conv-item', { active: currentConvId === conv.cid }]"
            @click="switchConversation(conv.cid)"
          >
            <svg class="conv-icon" viewBox="0 0 24 24" width="16" height="16"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="currentColor"/></svg>
            <span class="conv-title">{{ conv.title }}</span>
            <button class="btn-delete" @click.stop="handleDeleteConversation(conv.cid)" title="删除">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
            </button>
          </div>
          <div v-if="conversations.length === 0" class="empty-hint">暂无对话</div>
        </div>

        <div class="sidebar-footer">
          <button class="btn-memory" @click="showMemoryPanel = !showMemoryPanel">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/></svg>
            AI 记忆
          </button>
          <button class="btn-toggle" @click="sidebarCollapsed = !sidebarCollapsed" title="收起">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z" fill="currentColor"/></svg>
          </button>
        </div>
      </aside>

      <!-- 展开侧边栏按钮 -->
      <button v-if="sidebarCollapsed" class="btn-expand" @click="sidebarCollapsed = false">
        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="currentColor"/></svg>
      </button>

      <!-- 右侧：聊天主区域 -->
      <main class="chat-main">
        <!-- 空状态 -->
        <section v-if="!currentConvId" class="empty-state">
          <div class="empty-logo">
            <svg viewBox="0 0 24 24" width="48" height="48"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="#d1d5db"/></svg>
          </div>
          <h2 class="empty-title">CampusHub AI 助手</h2>
          <p class="empty-subtitle">我可以帮你搜索约伴活动、查看天气、搜索地点等</p>
          <div class="prompt-gallery" aria-label="快捷任务">
            <button
              v-for="item in promptStarters"
              :key="item.title"
              class="prompt-card"
              type="button"
              @click="startSuggestedPrompt(item.prompt)"
            >
              <span class="prompt-icon">{{ item.icon }}</span>
              <span class="prompt-main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </span>
            </button>
          </div>
          <button class="btn-start" @click="handleNewConversation">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
            开始新对话
          </button>
        </section>

        <!-- 对话区域 -->
        <section v-else class="chat-area">
          <div class="messages-container" ref="chatContainer" @click="handleChatClick" @pointerdown="handleChatPointerDown">
            <div v-if="messages.length === 0" class="chat-empty-state">
              <div class="chat-empty-icon">
                <svg viewBox="0 0 24 24" width="30" height="30"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z" fill="currentColor"/></svg>
              </div>
              <h3>新的对话</h3>
              <p>输入活动、天气、地点或校园服务问题，CampusHub 会帮你继续查找。</p>
              <div class="quick-prompts" aria-label="建议问题">
                <button
                  v-for="item in promptStarters"
                  :key="`quick-${item.title}`"
                  class="quick-prompt"
                  type="button"
                  @click="startSuggestedPrompt(item.prompt)"
                >
                  {{ item.title }}
                </button>
              </div>
            </div>
            <div v-else class="messages-inner">
              <div v-for="message in messages" :key="message.mid" :class="['message-item', message.role]">
                <template v-if="message.role !== 'tool'">
                  <!-- 用户消息 -->
                  <div v-if="message.role === 'user'" class="user-message">
                    <div class="user-message-text">{{ message.content }}</div>
                  </div>
                  <!-- AI 消息 -->
                  <div v-else class="assistant-message">
                    <div class="assistant-avatar">
                      <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" fill="currentColor"/></svg>
                    </div>
                    <div class="assistant-content">
                      <div
                        v-if="message.operations?.length"
                        :class="['operation-timeline', { completed: !message.loading && message.content }]"
                      >
                        <div v-if="!message.loading && message.content" class="operation-summary-head">
                          <span>执行摘要</span>
                          <span>{{ message.operations.length }} 步</span>
                        </div>
                        <div
                          v-for="(operation, opIndex) in message.operations"
                          :key="`${message.mid || message.localId || 'msg'}-${opIndex}`"
                          :class="['operation-step', operation.state || 'running']"
                        >
                          <span class="operation-dot"></span>
                          <div class="operation-main">
                            <div class="operation-title">{{ operation.title }}</div>
                            <div v-if="operation.detail" class="operation-detail">{{ operation.detail }}</div>
                          </div>
                        </div>
                      </div>
                      <div v-if="message.artifacts?.length" class="artifact-list">
                        <div
                          v-for="(artifact, artifactIndex) in message.artifacts"
                          :key="`${message.mid || message.localId || 'msg'}-artifact-${artifactIndex}`"
                          :class="['artifact-card', `artifact-${artifact.type || 'generic'}`]"
                        >
                          <div class="artifact-header">
                            <div class="artifact-icon">{{ artifact.type === 'confirmation' ? '!' : 'i' }}</div>
                            <div class="artifact-heading">
                              <div class="artifact-title">{{ artifact.title || '结果卡片' }}</div>
                              <div v-if="artifact.description" class="artifact-description">{{ artifact.description }}</div>
                            </div>
                          </div>
                          <div v-if="artifact.fields?.length && !artifact.editing" class="artifact-fields">
                            <div
                              v-for="(field, fieldIndex) in artifact.fields"
                              :key="fieldIndex"
                              :class="['artifact-field', { missing: field.missing }]"
                            >
                              <span class="artifact-field-label">{{ field.label }}</span>
                              <span class="artifact-field-value">{{ formatArtifactValue(field.value) }}</span>
                            </div>
                          </div>
                          <div v-if="artifact.editing" class="artifact-editor">
                            <label
                              v-for="(field, fieldIndex) in artifact.fields"
                              :key="`edit-${fieldIndex}`"
                              class="artifact-edit-field"
                            >
                              <span>{{ field.label }}</span>
                              <textarea v-model="field.editValue" rows="2" :placeholder="field.missing ? '补充这个信息' : '修改内容'"></textarea>
                            </label>
                          </div>
                          <div v-if="artifact.type === 'confirmation'" class="artifact-actions">
                            <template v-if="artifact.editing">
                              <button class="artifact-action primary" :disabled="sending" @click="handleArtifactAction(artifact, 'confirm-edited')">
                                保存并确认
                              </button>
                              <button class="artifact-action ghost" :disabled="sending" @click="handleArtifactAction(artifact, 'cancel-edit')">
                                退出编辑
                              </button>
                            </template>
                            <template v-else>
                              <button
                                class="artifact-action primary"
                                :disabled="sending || artifactHasMissingFields(artifact)"
                                :title="artifactHasMissingFields(artifact) ? '请先点击修改草稿补充缺失信息' : ''"
                                @click="handleArtifactAction(artifact, 'confirm')"
                              >
                                {{ artifactHasMissingFields(artifact) ? '补充后确认' : '确认执行' }}
                              </button>
                              <button class="artifact-action" :disabled="sending" @click="handleArtifactAction(artifact, 'edit')">
                                修改草稿
                              </button>
                              <button class="artifact-action ghost" :disabled="sending" @click="handleArtifactAction(artifact, 'cancel')">
                                取消
                              </button>
                            </template>
                          </div>
                          <div v-else-if="artifact.actions?.length" class="artifact-actions artifact-prompt-actions">
                            <button
                              v-for="(action, actionIndex) in artifact.actions"
                              :key="`${artifactIndex}-action-${actionIndex}`"
                              :class="['artifact-action', { primary: action.primary }]"
                              :disabled="sending"
                              @click="handleArtifactPromptAction(action)"
                            >
                              {{ action.label || '执行' }}
                            </button>
                          </div>
                        </div>
                      </div>
                      <div v-if="message.loading" class="loading-dots">
                        <span></span><span></span><span></span>
                      </div>
                      <template v-else>
                        <div v-if="message.status && !message.content" class="status-text">{{ message.status }}</div>
                        <div class="markdown-body" v-html="formatContent(message.content)"></div>
                        <div v-if="getFollowupSuggestions(message).length" class="reply-actions" aria-label="下一步建议">
                          <button
                            v-for="suggestion in getFollowupSuggestions(message)"
                            :key="suggestion.label"
                            class="reply-action"
                            type="button"
                            :disabled="sending"
                            @click="startSuggestedPrompt(suggestion.prompt)"
                          >
                            <span>{{ suggestion.icon }}</span>
                            {{ suggestion.label }}
                          </button>
                        </div>
                      </template>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-wrapper">
              <textarea
                ref="textareaRef"
                v-model="inputMessage"
                @keydown="handleKeydown"
                @input="autoResize"
                placeholder="给 CampusHub 发消息... (Enter 发送, Shift+Enter 换行)"
                rows="1"
                :disabled="sending"
              ></textarea>
              <button
                class="btn-send"
                @click="handleSendMessage"
                :disabled="sending || !inputMessage.trim()"
                :class="{ active: inputMessage.trim() && !sending }"
              >
                <svg viewBox="0 0 24 24" width="20" height="20"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"/></svg>
              </button>
            </div>
            <div class="input-hint">CampusHub 可能会犯错，请核实重要信息</div>
          </div>
        </section>
      </main>
    </div>

    <!-- 记忆面板 -->
    <el-drawer
      v-model="showMemoryPanel"
      class="memory-drawer"
      title="AI 对你的了解"
      direction="rtl"
      :size="memoryDrawerSize"
    >
      <div class="memory-panel">
        <div v-if="memories.length === 0" class="memory-empty">AI 还没有记住关于你的任何信息</div>
        <div v-for="mem in memories" :key="mem.memId" class="memory-item">
          <div class="memory-item-head">
            <div class="memory-tag">{{ mem.category }}</div>
            <button class="memory-delete" @click="handleDeleteMemory(mem.memId)" title="删除此记忆" aria-label="删除此记忆">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
            </button>
          </div>
          <div class="memory-content">{{ mem.content }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import agentService from '../services/agent'
import { readAgentStreamStates, subscribeAgentStreamStates, writeAgentStreamStates } from '../services/agentStreamState'

const router = useRouter()

const chatContainer = ref(null)
const textareaRef = ref(null)

const conversations = ref([])
const currentConvId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const sidebarCollapsed = ref(false)
const showMemoryPanel = ref(false)
const memories = ref([])
const wasMobileViewport = ref(false)
const memoryDrawerSize = computed(() => (wasMobileViewport.value ? '100%' : '420px'))
let activeStreamController = null
let streamStateUnsubscribe = null
let streamStateReloading = false

const COMPLETED_UI_STATE_KEY = 'campushub_ai_completed_ui_states'
const COMPLETED_UI_STATE_TTL = 24 * 60 * 60 * 1000
const COMPLETED_UI_STATE_LIMIT = 30
const COMPLETED_UI_ITEMS_PER_CONVERSATION = 8

const promptStarters = [
  {
    icon: '约',
    title: '找约伴活动',
    description: '按校区、时间和运动类型筛选',
    prompt: '帮我看看良乡校区今天有没有适合加入的篮球或羽毛球约伴活动'
  },
  {
    icon: '图',
    title: '附近推荐',
    description: '找店铺、地点并展示地图',
    prompt: '我想找适合三个人一起去的按摩店，请推荐附近店铺并展示地图'
  },
  {
    icon: '稿',
    title: '发布草稿',
    description: '先生成确认卡片再执行',
    prompt: '帮我发一条动态：今晚七点图书馆二楼自习，欢迎同学一起加入'
  },
  {
    icon: '天',
    title: '天气建议',
    description: '结合天气判断是否适合出行',
    prompt: '查一下今天北京天气，适不适合晚上去操场跑步'
  }
]

function uniqSuggestions(items) {
  const seen = new Set()
  return items.filter(item => {
    if (!item?.label || !item?.prompt || seen.has(item.label)) return false
    seen.add(item.label)
    return true
  }).slice(0, 4)
}

function getFollowupSuggestions(message) {
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
  const hasMap = /地图|附近|路线|店|餐厅|影院|按摩|地点|地址|map-card|高德/.test(content)
  const hasWeather = /天气|温度|下雨|风|户外|跑步|出行/.test(content)
  const hasOrder = /约伴|订单|活动|报名|加入|篮球|羽毛球|自习/.test(content)
  const hasContent = /动态|评论|点赞|帖子|发布/.test(content)

  if (hasMap) {
    suggestions.push(
      { icon: '换', label: '换一批附近推荐', prompt: '换一批附近推荐，并继续展示地图' },
      { icon: '约', label: '基于这个地点创建约伴', prompt: '基于刚才推荐的地点，帮我整理一个约伴活动草稿' }
    )
  }
  if (hasWeather) {
    suggestions.push({ icon: '备', label: '给我备选安排', prompt: '如果天气不适合，帮我推荐一个室内备选安排' })
  }
  if (hasOrder) {
    suggestions.push(
      { icon: '筛', label: '只看可加入活动', prompt: '只筛选我现在还能加入的约伴活动' },
      { icon: '发', label: '帮我发起一个约伴', prompt: '帮我根据刚才的信息生成一个新的约伴活动草稿' }
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

function parseAgentEventData(data) {
  if (!data) return {}
  if (typeof data !== 'string') return data
  try {
    return JSON.parse(data)
  } catch (e) {
    return { title: data }
  }
}

function formatIntentDetail(payload) {
  const parts = []
  if (payload.primary_intent) parts.push(payload.primary_intent)
  if (payload.operation_type) parts.push(payload.operation_type)
  if (typeof payload.confidence === 'number') parts.push(`置信度 ${Math.round(payload.confidence * 100)}%`)
  if (payload.requires_confirmation) parts.push('需要确认')
  return parts.join(' · ')
}

function normalizeAgentOperation(eventName, data) {
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

function normalizeArtifact(eventName, data) {
  const payload = parseAgentEventData(data)
  const type = payload.type || (eventName === 'confirm_required' ? 'confirmation' : 'generic')
  const fields = Array.isArray(payload.fields) ? payload.fields : []
  const actions = Array.isArray(payload.actions) ? payload.actions : []
  return {
    ...payload,
    type,
    fields: fields.map(field => {
      const normalized = field && typeof field === 'object' ? field : { label: '信息', value: field }
      return {
        ...normalized,
        editValue: formatArtifactValue(normalized.value) === '未填写' ? '' : formatArtifactValue(normalized.value)
      }
    }),
    actions: actions
      .map(action => action && typeof action === 'object' ? action : { label: String(action || ''), prompt: String(action || '') })
      .filter(action => action.label || action.prompt),
    editing: false
  }
}

function readStreamStates() {
  return readAgentStreamStates()
}

function writeStreamStates(states) {
  writeAgentStreamStates(states)
}

function getStoredStreamState(cid) {
  if (!cid) return null
  return readStreamStates()[String(cid)] || null
}

function toPlainStreamValue(value, fallback) {
  try {
    return JSON.parse(JSON.stringify(value ?? fallback))
  } catch (e) {
    return fallback
  }
}

function snapshotAssistantMessage(message, state = 'running') {
  return {
    mid: message.mid,
    localId: message.localId,
    role: 'assistant',
    content: message.content || '',
    status: message.status || '',
    loading: state === 'running',
    operations: toPlainStreamValue(message.operations, []),
    artifacts: toPlainStreamValue(message.artifacts, [])
  }
}

function saveStreamState(cid, assistantMsg, userText, state = 'running') {
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

function getLocalJson(key, fallback = {}) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch (e) {
    return fallback
  }
}

function setLocalJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (e) {
    // ignore storage quota/privacy errors; live UI still works in memory
  }
}

function finalizeOperationSummary(operations = []) {
  return toPlainStreamValue(operations, [])
    .slice(-10)
    .map(operation => ({
      ...operation,
      state: operation.state === 'running' ? 'completed' : (operation.state || 'completed')
    }))
}

function readCompletedUiStates() {
  const now = Date.now()
  const states = getLocalJson(COMPLETED_UI_STATE_KEY, {})
  const entries = Object.entries(states)
    .filter(([, value]) => value?.updatedAt && now - Number(value.updatedAt) < COMPLETED_UI_STATE_TTL)
    .sort((a, b) => Number(b[1].updatedAt) - Number(a[1].updatedAt))
    .slice(0, COMPLETED_UI_STATE_LIMIT)
  return Object.fromEntries(entries)
}

function writeCompletedUiStates(states) {
  setLocalJson(COMPLETED_UI_STATE_KEY, states)
}

function saveCompletedUiState(cid, assistantMsg, userText) {
  if (!cid || !assistantMsg) return
  const operations = finalizeOperationSummary(assistantMsg.operations || [])
  const artifacts = toPlainStreamValue(assistantMsg.artifacts, [])
  if (!operations.length && !artifacts.length) return

  const states = readCompletedUiStates()
  const key = String(cid)
  const previous = states[key] || {}
  const previousItems = Array.isArray(previous.items)
    ? previous.items
    : (previous.assistant ? [{
        userText: previous.userText,
        updatedAt: previous.updatedAt,
        assistant: previous.assistant
      }] : [])

  const item = {
    userText,
    updatedAt: Date.now(),
    assistant: {
      operations,
      artifacts,
      contentPreview: String(assistantMsg.content || '').slice(0, 120)
    }
  }
  const itemKey = `${String(userText || '')}::${item.assistant.contentPreview}`
  const items = [
    item,
    ...previousItems.filter(existing =>
      `${String(existing?.userText || '')}::${String(existing?.assistant?.contentPreview || '')}` !== itemKey
    )
  ].slice(0, COMPLETED_UI_ITEMS_PER_CONVERSATION)

  states[key] = {
    cid,
    updatedAt: item.updatedAt,
    items
  }
  const trimmed = Object.fromEntries(
    Object.entries(states)
      .sort((a, b) => Number(b[1].updatedAt) - Number(a[1].updatedAt))
      .slice(0, COMPLETED_UI_STATE_LIMIT)
  )
  writeCompletedUiStates(trimmed)
}

function mergeCompletedUiState(cid) {
  const state = readCompletedUiStates()[String(cid)]
  const items = Array.isArray(state?.items)
    ? state.items
    : (state?.assistant ? [{
        userText: state.userText,
        updatedAt: state.updatedAt,
        assistant: state.assistant
      }] : [])
  if (!items.length) return false

  let applied = 0
  messages.value.forEach((target, targetIndex) => {
    if (target.role !== 'assistant') return
    const previousUser = [...messages.value]
      .slice(0, targetIndex)
      .reverse()
      .find(message => message.role === 'user')
    const matched = items.find(item => {
      const assistant = item?.assistant || {}
      const preview = String(assistant.contentPreview || '')
      const userMatches = !item.userText || !previousUser?.content || previousUser.content === item.userText
      const contentMatches = !preview || String(target.content || '').startsWith(preview)
      return userMatches && contentMatches
    })
    const assistant = matched?.assistant
    if (!assistant) return
    if (assistant.operations?.length && !target.operations?.length) {
      target.operations = toPlainStreamValue(assistant.operations, [])
    }
    if (assistant.artifacts?.length && !target.artifacts?.length) {
      target.artifacts = toPlainStreamValue(assistant.artifacts, [])
    }
    target.uiRestored = true
    applied += 1
  })
  return applied > 0
}

function clearStreamState(cid) {
  if (!cid) return
  const states = readStreamStates()
  delete states[String(cid)]
  writeStreamStates(states)
}

function appendStoredStreamMessage(cid) {
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

function handleStreamStateChange() {
  const cid = currentConvId.value
  if (!cid) return

  if (appendStoredStreamMessage(cid)) return

  const needsFinalRefresh = messages.value.some(item => item.restored && item.loading)
  if (!needsFinalRefresh || streamStateReloading) return

  streamStateReloading = true
  switchConversation(cid).finally(() => {
    streamStateReloading = false
  })
}

function applyAgentArtifact(message, eventName, data) {
  if (!message.artifacts) message.artifacts = []
  const artifact = normalizeArtifact(eventName, data)
  const key = artifact.id || `${artifact.type}:${artifact.title || ''}:${artifact.actionKind || ''}`
  const exists = message.artifacts.some(item => (item.id || `${item.type}:${item.title || ''}:${item.actionKind || ''}`) === key)
  if (!exists) {
    message.artifacts.push(artifact)
  }
}

function applyAgentEvent(message, eventName, data) {
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

function formatArtifactValue(value) {
  if (value === null || value === undefined || value === '') return '未填写'
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function artifactHasMissingFields(artifact) {
  return (artifact?.fields || []).some(field => {
    if (field?.missing) return true
    const value = formatArtifactValue(field?.value)
    return value === '待补充' || value === '未填写'
  })
}

async function sendMessageText(text) {
  if (!text || sending.value) return
  inputMessage.value = text
  await nextTick()
  await handleSendMessage()
}

function handleArtifactAction(artifact, action) {
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
    confirm: buildArtifactConfirmMessage(artifact, false),
    'confirm-edited': buildArtifactConfirmMessage(artifact, true),
    cancel: artifact?.cancelMessage || `取消这个草稿：${title}`
  }
  sendMessageText(messages[action])
}

function handleArtifactPromptAction(action) {
  const prompt = String(action?.prompt || '').trim()
  if (!prompt) return
  sendMessageText(prompt)
}

function buildArtifactConfirmMessage(artifact, edited = false) {
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

const syncSidebarForViewport = () => {
  if (typeof window === 'undefined') return
  const isMobileViewport = window.innerWidth <= 768
  if (isMobileViewport && !wasMobileViewport.value) {
    sidebarCollapsed.value = true
  }
  if (!isMobileViewport && wasMobileViewport.value) {
    sidebarCollapsed.value = false
  }
  wasMobileViewport.value = isMobileViewport
}

try { inputMessage.value = localStorage.getItem('ai_draft') || '' } catch (e) { /* ignore */ }

// ==================== 会话管理 ====================

async function loadConversations() {
  try {
    const resp = await agentService.listConversations()
    conversations.value = resp.data?.data || []
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

async function handleNewConversation() {
  try {
    const resp = await agentService.createConversation()
    const conv = resp.data?.data
    if (conv) {
      conversations.value.unshift(conv)
      await switchConversation(conv.cid)
    }
  } catch (e) {
    ElMessage.error('创建会话失败')
  }
}

async function startSuggestedPrompt(prompt) {
  if (!prompt || sending.value) return
  inputMessage.value = prompt
  await nextTick()
  await handleSendMessage()
}

async function switchConversation(cid) {
  currentConvId.value = cid
  messages.value = []
  try {
    const resp = await agentService.getMessages(cid)
    const rawMessages = resp.data?.data || []
    messages.value = rawMessages.map(m => ({ ...m, loading: false }))
    mergeCompletedUiState(cid)
    const stored = getStoredStreamState(cid)
    const latestSaved = rawMessages[rawMessages.length - 1]
    if (stored && latestSaved?.role === 'assistant' && latestSaved?.content) {
      clearStreamState(cid)
    } else if (stored && Date.now() - Number(stored.updatedAt || 0) < 10 * 60 * 1000) {
      appendStoredStreamMessage(cid)
    } else if (stored) {
      clearStreamState(cid)
    }
    scrollToBottom()
  } catch (e) {
    ElMessage.error('加载消息失败')
  }
}

async function handleDeleteConversation(cid) {
  try {
    await ElMessageBox.confirm('确定删除这个对话吗？', '提示', { type: 'warning' })
    await agentService.deleteConversation(cid)
    conversations.value = conversations.value.filter(c => c.cid !== cid)
    if (currentConvId.value === cid) {
      currentConvId.value = null
      messages.value = []
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ==================== 消息发送 ====================

async function handleSendMessage() {
  if (!inputMessage.value.trim() || sending.value) return

  if (!currentConvId.value) {
    await handleNewConversation()
    if (!currentConvId.value) return
  }

  const userMsg = { mid: Date.now(), role: 'user', content: inputMessage.value, loading: false }
  messages.value.push(userMsg)
  const msgText = inputMessage.value
  inputMessage.value = ''
  try { localStorage.removeItem('ai_draft') } catch (e) { /* ignore */ }
  resetTextareaHeight()
  scrollToBottom()

  const aiMsg = { mid: Date.now() + 1, role: 'assistant', content: '', loading: true, operations: [], artifacts: [] }
  messages.value.push(aiMsg)
  applyAgentEvent(aiMsg, 'agent_step', JSON.stringify({
    phase: 'client',
    title: '已发送消息',
    detail: '正在建立 AI 流式连接并等待智能体调度',
    state: 'running'
  }))
  saveStreamState(currentConvId.value, aiMsg, msgText)
  scrollToBottom()

  sending.value = true
  let doneReceived = false

  const streamCid = currentConvId.value
  activeStreamController = agentService.streamMessage(streamCid, msgText, {
    onDelta(text) {
      if (aiMsg.loading) aiMsg.loading = false
      if (aiMsg.status) aiMsg.status = ''  // 收到实际内容后清除 status
      aiMsg.content += text
      saveStreamState(streamCid, aiMsg, msgText)
      scrollToBottom()
    },
    onStatus(statusText) {
      if (aiMsg.loading) aiMsg.loading = false
      applyAgentEvent(aiMsg, 'status', statusText)
      saveStreamState(streamCid, aiMsg, msgText)
      scrollToBottom()
    },
    onEvent(eventName, data) {
      if (aiMsg.loading) aiMsg.loading = false
      applyAgentEvent(aiMsg, eventName, data)
      saveStreamState(streamCid, aiMsg, msgText)
      scrollToBottom()
    },
    async onDone() {
      if (doneReceived) return
      doneReceived = true
      aiMsg.loading = false
      if (!aiMsg.content) aiMsg.content = '抱歉，AI 未返回有效内容。'
      sending.value = false
      activeStreamController = null
      saveCompletedUiState(streamCid, aiMsg, msgText)
      clearStreamState(streamCid)
      scrollToBottom()
      await loadConversations()
      if (currentConvId.value === streamCid) {
        await switchConversation(streamCid)
      }
    },
    onError(errMsg) {
      aiMsg.loading = false
      aiMsg.content = `错误：${errMsg}`
      sending.value = false
      activeStreamController = null
      saveStreamState(streamCid, aiMsg, msgText, 'error')
      scrollToBottom()
    }
  })
}

// ==================== 记忆管理 ====================

async function loadMemories() {
  try {
    const resp = await agentService.getMemories()
    memories.value = resp.data?.data || []
  } catch (e) {
    console.error('加载记忆失败', e)
  }
}

async function handleDeleteMemory(memId) {
  try {
    await agentService.deleteMemory(memId)
    memories.value = memories.value.filter(m => m.memId !== memId)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

watch(showMemoryPanel, (val) => { if (val) loadMemories() })

// ==================== 工具函数 ====================

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      return // 换行
    }
    e.preventDefault()
    handleSendMessage()
  }
}

function autoResize() {
  const ta = textareaRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  try { localStorage.setItem('ai_draft', inputMessage.value) } catch (e) { /* ignore */ }
}

function resetTextareaHeight() {
  nextTick(() => {
    const ta = textareaRef.value
    if (ta) ta.style.height = 'auto'
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
      tiles.push(`<img class="map-tile" alt="" loading="lazy" draggable="false" src="${getAmapTileUrl(x, y, zoom)}" />`)
    }
  }

  return { tiles: tiles.join(''), pointX, pointY }
}

const renderMapCard = (props = {}) => {
  const lng = Number.parseFloat(props.lng)
  const lat = Number.parseFloat(props.lat)
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return ''

  const zoom = clampNumber(Number.parseInt(props.zoom || '15', 10) || 15, 3, 18)
  const title = props.title || props.name || '位置'
  const grid = buildMapTileGrid(lng, lat, zoom)

  const markerUrl = `https://uri.amap.com/marker?position=${lng},${lat}&name=${encodeURIComponent(title)}&coordinate=gaode&callnative=0`
  return `<div class="map-card" data-lng="${lng}" data-lat="${lat}" data-zoom="${zoom}" data-title="${escapeHtml(title)}">` +
    `<div class="map-tile-stage" aria-label="${escapeHtml(title)}地图预览" data-map-stage="true">` +
      `<div class="map-tile-grid" style="left:calc(50% - ${grid.pointX}px);top:calc(50% - ${grid.pointY}px);">${grid.tiles}</div>` +
      `<div class="map-pin" title="${escapeHtml(title)}">` +
        `<svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true"><path d="M12 2C8.42 2 5.5 4.92 5.5 8.5c0 4.88 6.5 13.5 6.5 13.5s6.5-8.62 6.5-13.5C18.5 4.92 15.58 2 12 2zm0 8.8a2.3 2.3 0 1 1 0-4.6 2.3 2.3 0 0 1 0 4.6z" fill="currentColor"/></svg>` +
      `</div>` +
      `<div class="map-badge">高德地图预览</div>` +
      `<div class="map-controls" aria-label="地图控制">` +
        `<button type="button" class="map-control" data-map-action="zoom-in" title="放大">+</button>` +
        `<button type="button" class="map-control" data-map-action="zoom-out" title="缩小">-</button>` +
        `<button type="button" class="map-control" data-map-action="north" title="向上">↑</button>` +
        `<button type="button" class="map-control" data-map-action="south" title="向下">↓</button>` +
        `<button type="button" class="map-control" data-map-action="west" title="向左">←</button>` +
        `<button type="button" class="map-control" data-map-action="east" title="向右">→</button>` +
      `</div>` +
    `</div>` +
    `<div class="map-card-meta">` +
      `<div class="map-card-info">` +
        `<div class="map-card-title">${escapeHtml(title)}</div>` +
        `<div class="map-card-coords">${lng.toFixed(6)}, ${lat.toFixed(6)} · zoom ${zoom}</div>` +
      `</div>` +
      `<div class="map-card-actions">` +
        `<button type="button" class="map-card-action map-card-draft" data-map-intent="order-draft">用此地点约伴</button>` +
        `<a href="${escapeHtml(markerUrl)}" target="_blank" rel="noopener noreferrer" class="map-card-action">打开高德地图</a>` +
      `</div>` +
    `</div>` +
    `<div class="map-card-hint">可拖拽地图，也可以使用缩放和平移按钮。</div>` +
  `</div>`
}

const renderEntityLinkCard = (url = '', text = '') => {
  const orderDetail = url.match(/^\/orders\/(\d+)$/)
  const contentDetail = url.match(/^\/contents\/(\d+)$/)
  const cards = {
    orders: {
      type: 'order',
      icon: '约',
      title: text || '查看约伴活动',
      subtitle: '浏览可加入的校园约伴订单',
      action: '打开列表'
    },
    contents: {
      type: 'content',
      icon: '动',
      title: text || '查看校园动态',
      subtitle: '浏览同学发布的校园动态',
      action: '打开列表'
    }
  }

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
    meta = cards.orders
  } else if (url === '/contents') {
    meta = cards.contents
  }

  if (!meta) return ''
  return `<a href="${escapeHtml(url)}" class="app-link entity-link-card entity-${meta.type}" data-route="${escapeHtml(url)}">` +
    `<span class="entity-icon">${meta.icon}</span>` +
    `<span class="entity-main">` +
      `<strong class="entity-title">${meta.title}</strong>` +
      `<span class="entity-subtitle">${meta.subtitle}</span>` +
    `</span>` +
    `<span class="entity-action">${meta.action}</span>` +
  `</a>`
}

const getExecutionMeta = (message = '', url = '') => {
  const text = String(message || '').trim()
  const orderId = (url.match(/^\/orders\/(\d+)$/) || text.match(/订单\s*#?(\d+)/))?.[1]
  const contentId = (url.match(/^\/contents\/(\d+)$/) || text.match(/动态\s*#?(\d+)/))?.[1]
  const route = url || (orderId ? `/orders/${orderId}` : contentId ? `/contents/${contentId}` : '')

  if (/约伴订单创建成功|订单创建成功/.test(text)) {
    return {
      type: 'order',
      icon: '约',
      title: '约伴订单已创建',
      subtitle: orderId ? `订单 #${orderId} 已发布，正在等待同学加入` : '订单已发布，正在等待同学加入',
      action: '查看订单',
      route
    }
  }
  if (/动态发布成功/.test(text)) {
    return {
      type: 'content',
      icon: '动',
      title: '动态已发布',
      subtitle: contentId ? `动态 #${contentId} 已同步到校园动态` : '已同步到校园动态',
      action: '查看动态',
      route
    }
  }
  if (/评论发表成功/.test(text)) {
    return {
      type: 'comment',
      icon: '评',
      title: '评论已发表',
      subtitle: contentId ? `已评论动态 #${contentId}` : '评论已写入动态',
      action: '查看动态',
      route
    }
  }
  if (/操作成功/.test(text) && route.startsWith('/contents/')) {
    return {
      type: 'like',
      icon: '赞',
      title: '动态操作已完成',
      subtitle: contentId ? `动态 #${contentId} 的点赞状态已更新` : '点赞状态已更新',
      action: '查看动态',
      route
    }
  }
  if (/申请加入订单/.test(text)) {
    return {
      type: 'order',
      icon: '报',
      title: '申请已提交',
      subtitle: orderId ? `订单 #${orderId} 正在等待发布者审核` : '正在等待发布者审核',
      action: '查看订单',
      route
    }
  }
  if (/已接受用户加入订单/.test(text)) {
    return {
      type: 'order',
      icon: '审',
      title: '申请已接受',
      subtitle: orderId ? `订单 #${orderId} 已进入后续约伴流程` : '订单已进入后续约伴流程',
      action: '查看订单',
      route
    }
  }
  if (/已标记为完成/.test(text)) {
    return {
      type: 'order',
      icon: '完',
      title: '订单已完成',
      subtitle: orderId ? `订单 #${orderId} 已更新为完成状态` : '订单状态已更新为完成',
      action: '查看订单',
      route
    }
  }
  return null
}

const renderExecutionResultCard = (message = '', url = '') => {
  const meta = getExecutionMeta(message, url)
  if (!meta) return ''
  const action = meta.route
    ? `<button type="button" class="app-link execution-action" data-route="${escapeHtml(meta.route)}">${escapeHtml(meta.action)}</button>`
    : ''
  return `<div class="execution-result-card execution-${meta.type}">` +
    `<span class="execution-icon">${escapeHtml(meta.icon)}</span>` +
    `<span class="execution-main">` +
      `<strong class="execution-title">${escapeHtml(meta.title)}</strong>` +
      `<span class="execution-subtitle">${escapeHtml(meta.subtitle)}</span>` +
    `</span>` +
    action +
  `</div>`
}

const renderMarkdown = (md) => {
  if (!md) return ''

  const mapBlocks = []
  md = md.replace(/:{2,}map\{([^}]+)\}/g, (match, attrs) => {
    const idx = mapBlocks.length
    mapBlocks.push(parseMapAttrs(attrs))
    return `@@MAP_BLOCK_${idx}@@`
  })

  const executionBlocks = []
  md = md.replace(/^✅\s*(.+?)(?:\s*\[([^\]]+)\]\((\/(?:orders|contents)\/\d+)\))?\s*$/gm, (match, message, linkText, url) => {
    const card = renderExecutionResultCard(message, url || '')
    if (!card) return match
    const idx = executionBlocks.length
    executionBlocks.push(card)
    return `@@EXECUTION_BLOCK_${idx}@@`
  })

  const codeBlocks = []
  md = md.replace(/```([\s\S]*?)```/g, (m, code) => {
    const idx = codeBlocks.length
    codeBlocks.push(code)
    return `@@CODE_BLOCK_${idx}@@`
  })

  md = escapeHtml(md)

  md = md.replace(/^###\s*(.*)$/gm, '<h3>$1</h3>')
  md = md.replace(/^##\s*(.*)$/gm, '<h2>$1</h2>')
  md = md.replace(/^#\s*(.*)$/gm, '<h1>$1</h1>')

  md = md.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
    if (url.startsWith('/')) {
      const entityCard = renderEntityLinkCard(url, text)
      if (entityCard) return entityCard
      return `<a href="${url}" class="app-link" data-route="${url}">${text}</a>`
    }
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`
  })

  md = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  md = md.replace(/\*(.+?)\*/g, '<em>$1</em>')
  md = md.replace(/`([^`]+)`/g, '<code>$1</code>')

  // 有序列表
  md = md.replace(/(^|\n)((?:\d+\.\s+.+\n?)+)/g, (m) => {
    const items = m.trim().split(/\n/).filter(Boolean).map(l => l.replace(/^\d+\.\s+/, ''))
    return '\n<ol>' + items.map(i => '<li>' + i + '</li>').join('') + '</ol>'
  })
  // 无序列表
  md = md.replace(/(^|\n)((?:[ \t]*[-\*]\s+.+\n?)+)/g, (m) => {
    const items = m.trim().split(/\n/).filter(Boolean).map(l => l.replace(/^[ \t]*[-\*]\s+/, ''))
    return '\n<ul>' + items.map(i => '<li>' + i + '</li>').join('') + '</ul>'
  })

  md = md.replace(/@@EXECUTION_BLOCK_(\d+)@@/g, (m, idx) => executionBlocks[Number(idx)] || '')

  const parts = md.split(/\n\s*\n/)
  md = parts.map(p => {
    const s = p.replace(/\n/g, '<br/>')
    return /^<(h\d|ul|ol|pre|blockquote|div)/.test(s) ? s : ('<p>' + s + '</p>')
  }).join('\n')

  md = md.replace(/@@CODE_BLOCK_(\d+)@@/g, (m, idx) => {
    const code = codeBlocks[Number(idx)] || ''
    return '<pre><code>' + escapeHtml(code) + '</code></pre>'
  })

  // Models sometimes wrap map directives in backticks. Render them as maps, not code.
  md = md.replace(/<pre><code>\s*@@MAP_BLOCK_(\d+)@@\s*<\/code><\/pre>/g, '@@MAP_BLOCK_$1@@')
  md = md.replace(/<code>\s*@@MAP_BLOCK_(\d+)@@\s*<\/code>/g, '@@MAP_BLOCK_$1@@')

  md = md.replace(/@@MAP_BLOCK_(\d+)@@/g, (m, idx) => {
    const p = mapBlocks[Number(idx)]
    return renderMapCard(p)
  })

  return md
}

const formatContent = (text) => {
  if (!text) return ''
  let cleaned = text
  // 清除可能混入的 status 前缀（历史数据兼容）
  cleaned = cleaned.replace(/^正在思考\.{0,3}/g, '')
  // 如果文本中有不完整的 :::map{ 语法（流式拼接中），显示加载提示
  cleaned = cleaned.replace(/:{2,}map\{[^}]*$/g, '<p style="color:#9ca3af">正在加载地图...</p>')
  return renderMarkdown(cleaned.trim())
}

function handleChatClick(e) {
  const control = e.target.closest('.map-control')
  if (control) {
    e.preventDefault()
    const card = control.closest('.map-card')
    updateMapCardByAction(card, control.dataset.mapAction)
    return
  }

  const mapIntent = e.target.closest('[data-map-intent]')
  if (mapIntent) {
    e.preventDefault()
    const card = mapIntent.closest('.map-card')
    sendMapIntent(card, mapIntent.dataset.mapIntent)
    return
  }

  const link = e.target.closest('.app-link')
  if (link) {
    e.preventDefault()
    const route = link.dataset.route
    if (route) router.push(route)
  }
}

function sendMapIntent(card, intent) {
  if (!card || !intent) return
  const title = card.dataset.title || '这个地点'
  const lng = Number.parseFloat(card.dataset.lng)
  const lat = Number.parseFloat(card.dataset.lat)
  const coordText = Number.isFinite(lng) && Number.isFinite(lat)
    ? `，地点坐标：${lng.toFixed(6)}, ${lat.toFixed(6)}`
    : ''
  if (intent === 'order-draft') {
    sendMessageText(`基于地图里的「${title}」创建一个约伴订单草稿${coordText}。请沿用刚才推荐请求里的活动类型、人数和校区信息；如果还缺少必要信息，只追问缺失项，不要直接发布。`)
  }
}

function tilePointToLngLat(x, y, zoom) {
  const scale = 2 ** zoom
  const lng = (x / scale) * 360 - 180
  const n = Math.PI - (2 * Math.PI * y) / scale
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))
  return { lng, lat }
}

function setMapCardView(card, lng, lat, zoom) {
  if (!card || !Number.isFinite(lng) || !Number.isFinite(lat) || !Number.isFinite(zoom)) return
  const nextZoom = clampNumber(Math.round(zoom), 3, 18)
  const nextLng = clampNumber(lng, -180, 180)
  const nextLat = clampNumber(lat, -85, 85)
  const grid = buildMapTileGrid(nextLng, nextLat, nextZoom)
  const gridEl = card.querySelector('.map-tile-grid')
  const coordsEl = card.querySelector('.map-card-coords')
  const actionEl = card.querySelector('.map-card-action')
  const title = card.dataset.title || '位置'

  card.dataset.lng = String(nextLng)
  card.dataset.lat = String(nextLat)
  card.dataset.zoom = String(nextZoom)
  if (gridEl) {
    gridEl.innerHTML = grid.tiles
    gridEl.style.left = `calc(50% - ${grid.pointX}px)`
    gridEl.style.top = `calc(50% - ${grid.pointY}px)`
  }
  if (coordsEl) {
    coordsEl.textContent = `${nextLng.toFixed(6)}, ${nextLat.toFixed(6)} · zoom ${nextZoom}`
  }
  if (actionEl) {
    actionEl.href = `https://uri.amap.com/marker?position=${nextLng},${nextLat}&name=${encodeURIComponent(title)}&coordinate=gaode&callnative=0`
  }
}

function updateMapCardByAction(card, action) {
  if (!card || !action) return
  const lng = Number.parseFloat(card.dataset.lng)
  const lat = Number.parseFloat(card.dataset.lat)
  const zoom = Number.parseInt(card.dataset.zoom || '15', 10)
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || !Number.isFinite(zoom)) return

  if (action === 'zoom-in') return setMapCardView(card, lng, lat, zoom + 1)
  if (action === 'zoom-out') return setMapCardView(card, lng, lat, zoom - 1)

  const point = lngLatToTilePoint(lng, lat, zoom)
  const step = 0.45
  const moves = {
    north: { x: 0, y: -step },
    south: { x: 0, y: step },
    west: { x: -step, y: 0 },
    east: { x: step, y: 0 }
  }
  const move = moves[action]
  if (!move) return
  const next = tilePointToLngLat(point.x + move.x, point.y + move.y, zoom)
  setMapCardView(card, next.lng, next.lat, zoom)
}

function handleChatPointerDown(e) {
  const stage = e.target.closest('.map-tile-stage')
  if (!stage) return
  const card = stage.closest('.map-card')
  if (!card) return
  e.preventDefault()

  const startX = e.clientX
  const startY = e.clientY
  const startLng = Number.parseFloat(card.dataset.lng)
  const startLat = Number.parseFloat(card.dataset.lat)
  const zoom = Number.parseInt(card.dataset.zoom || '15', 10)
  if (!Number.isFinite(startLng) || !Number.isFinite(startLat) || !Number.isFinite(zoom)) return
  const startPoint = lngLatToTilePoint(startLng, startLat, zoom)
  stage.classList.add('dragging')

  const handleMove = (moveEvent) => {
    const dx = (moveEvent.clientX - startX) / 256
    const dy = (moveEvent.clientY - startY) / 256
    const next = tilePointToLngLat(startPoint.x - dx, startPoint.y - dy, zoom)
    setMapCardView(card, next.lng, next.lat, zoom)
  }

  const handleUp = () => {
    stage.classList.remove('dragging')
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', handleUp)
    window.removeEventListener('pointercancel', handleUp)
  }

  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', handleUp, { once: true })
  window.addEventListener('pointercancel', handleUp, { once: true })
}

// ==================== 生命周期 ====================

onMounted(async () => {
  syncSidebarForViewport()
  window.addEventListener('resize', syncSidebarForViewport)
  streamStateUnsubscribe = subscribeAgentStreamStates(handleStreamStateChange)
  await loadConversations()
  if (conversations.value.length > 0) {
    await switchConversation(conversations.value[0].cid)
  }
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', syncSidebarForViewport)
  if (streamStateUnsubscribe) {
    streamStateUnsubscribe()
    streamStateUnsubscribe = null
  }
})
</script>

<style scoped>
.ai-view { width: 100%; height: calc(100vh - 60px); overflow: hidden; background: #fff; }
.ai-layout { display: flex; height: 100%; }

/* ==================== 侧边栏（浅色风格） ==================== */
.sidebar {
  width: 260px; min-width: 260px; background: #f9fafb; color: #111;
  border-right: 1px solid #e5e7eb;
  display: flex; flex-direction: column; transition: all 0.2s;
}
.sidebar.collapsed { width: 0; min-width: 0; overflow: hidden; border-right: none; }

.sidebar-header { padding: 12px; }
.btn-new-chat {
  width: 100%; display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px;
  background: #fff; color: #374151; cursor: pointer;
  font-size: 14px; transition: background 0.15s;
}
.btn-new-chat:hover { background: #f3f4f6; }

.conversation-list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.conv-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border-radius: 8px; cursor: pointer;
  margin-bottom: 2px; transition: background 0.15s; color: #4b5563;
}
.conv-item:hover { background: #f3f4f6; }
.conv-item.active { background: #e5e7eb; color: #111; }
.conv-icon { flex-shrink: 0; opacity: 0.4; }
.conv-title { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-delete {
  border: none; background: transparent; color: #9ca3af; cursor: pointer;
  padding: 2px; border-radius: 4px; display: flex; opacity: 0; transition: opacity 0.15s;
}
.conv-item:hover .btn-delete { opacity: 1; }
.btn-delete:hover { color: #ef4444; }
.empty-hint { text-align: center; color: #9ca3af; font-size: 13px; padding: 24px 0; }

.sidebar-footer {
  padding: 12px; border-top: 1px solid #e5e7eb;
  display: flex; gap: 8px; align-items: center;
}
.btn-memory {
  border: none; background: transparent; color: #6b7280; cursor: pointer;
  font-size: 13px; display: flex; align-items: center; gap: 4px;
  padding: 6px 10px; border-radius: 6px; flex: 1;
}
.btn-memory:hover { background: #f3f4f6; color: #111; }
.btn-toggle {
  border: none; background: transparent; color: #9ca3af; cursor: pointer;
  padding: 4px; border-radius: 4px; display: flex;
}
.btn-toggle:hover { background: #f3f4f6; }

.btn-expand {
  position: fixed; top: 80px; left: 8px; z-index: 10;
  border: 1px solid #e0e0e0; background: #fff; padding: 8px;
  border-radius: 8px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* ==================== 聊天主区域（ChatGPT 风格） ==================== */
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: #fff; }

.empty-state {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 14px; color: #6b7280;
  padding: 28px;
}
.empty-logo { opacity: 0.4; }
.empty-title { margin: 0; font-size: 22px; font-weight: 600; color: #111; }
.empty-subtitle { margin: 0; font-size: 14px; color: #9ca3af; }
.prompt-gallery {
  width: min(720px, 100%);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 8px 0 2px;
}
.prompt-card {
  min-height: 86px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
  color: #111827;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s, box-shadow 0.15s;
}
.prompt-card:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}
.prompt-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-weight: 700;
}
.prompt-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.prompt-main strong {
  font-size: 14px;
  line-height: 1.35;
  color: #111827;
}
.prompt-main small {
  font-size: 12px;
  line-height: 1.45;
  color: #6b7280;
}
.btn-start {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 20px; border: 1px solid #d1d5db; border-radius: 20px;
  background: #fff; color: #111; cursor: pointer; font-size: 14px;
  transition: all 0.15s;
}
.btn-start:hover { background: #f9fafb; border-color: #9ca3af; }

.chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* 消息列表 */
.messages-container { flex: 1; overflow-y: auto; }
.messages-inner { max-width: 768px; margin: 0 auto; padding: 24px 16px; }

.chat-empty-state {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
  text-align: center;
  color: var(--ch-muted, #6b7280);
}

.chat-empty-icon {
  width: 54px;
  height: 54px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ch-primary-soft, #eff6ff);
  color: var(--ch-primary, #2563eb);
}

.chat-empty-state h3 {
  margin: 0;
  color: var(--ch-text, #111827);
  font-size: 20px;
  letter-spacing: 0;
}

.chat-empty-state p {
  max-width: 360px;
  margin: 0;
  color: var(--ch-muted, #6b7280);
  font-size: 14px;
  line-height: 1.6;
}
.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 560px;
  margin-top: 4px;
}
.quick-prompt {
  min-height: 34px;
  padding: 7px 12px;
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.quick-prompt:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.message-item { margin-bottom: 24px; }

/* 用户消息 — 右对齐气泡 */
.user-message { display: flex; justify-content: flex-end; }
.user-message-text {
  max-width: 70%; padding: 12px 16px; border-radius: 18px 18px 4px 18px;
  background: #2563eb; color: #fff; font-size: 15px; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word;
}

/* AI 消息 — 左对齐，无气泡 */
.assistant-message { display: flex; gap: 12px; align-items: flex-start; }
.assistant-avatar {
  flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%;
  background: #f3f4f6; border: 1px solid #e5e7eb;
  display: flex; align-items: center; justify-content: center; color: #6b7280;
  margin-top: 2px;
}
.assistant-content { flex: 1; min-width: 0; font-size: 15px; line-height: 1.7; color: #111827; }

/* Loading dots */
.loading-dots { display: flex; gap: 4px; padding: 8px 0; }
.loading-dots span {
  width: 8px; height: 8px; border-radius: 50%; background: #9ca3af;
  animation: dot-pulse 1.4s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Agent operation timeline */
.operation-timeline {
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f9fafb;
}
.operation-timeline.completed {
  padding: 8px 10px;
  background: #f8fafc;
}
.operation-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 7px;
  margin-bottom: 2px;
  border-bottom: 1px solid #edf2f7;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}
.operation-step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 6px 0;
  color: #64748b;
}
.operation-timeline.completed .operation-step {
  padding: 4px 0;
}
.operation-step + .operation-step { border-top: 1px solid #edf2f7; }
.operation-dot {
  width: 8px;
  height: 8px;
  margin-top: 7px;
  border-radius: 50%;
  background: #94a3b8;
  flex: 0 0 8px;
}
.operation-step.running .operation-dot {
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}
.operation-step.completed .operation-dot { background: #16a34a; }
.operation-step.failed .operation-dot { background: #dc2626; }
.operation-step.pending .operation-dot { background: #d97706; }
.operation-main { min-width: 0; }
.operation-title {
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
}
.operation-detail {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.artifact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0 0 12px;
}
.artifact-card {
  max-width: 520px;
  padding: 14px;
  border: 1px solid #dbe5f3;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}
.artifact-confirmation {
  border-color: #bfdbfe;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}
.artifact-guide {
  border-color: #bae6fd;
  background: linear-gradient(180deg, #ffffff 0%, #f0f9ff 100%);
}
.artifact-guide .artifact-icon {
  background: #0f766e;
}
.artifact-header {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.artifact-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  flex: 0 0 24px;
}
.artifact-heading { min-width: 0; }
.artifact-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.4;
}
.artifact-description {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.artifact-fields {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.artifact-field {
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #edf2f7;
}
.artifact-field.missing {
  background: #fff7ed;
  border-color: #fed7aa;
}
.artifact-field-label {
  display: block;
  color: #64748b;
  font-size: 11px;
  line-height: 1.3;
}
.artifact-field-value {
  display: block;
  margin-top: 2px;
  color: #1e293b;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  word-break: break-word;
}
.artifact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.artifact-prompt-actions {
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}
.artifact-action {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}
.artifact-action.primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}
.artifact-action.ghost {
  color: #64748b;
}
.artifact-action:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #94a3b8;
}
.artifact-action.primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}
.artifact-action.ghost:hover:not(:disabled) {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #b45309;
}
.artifact-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.artifact-editor {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.artifact-edit-field {
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
.artifact-edit-field textarea {
  width: 100%;
  min-height: 54px;
  resize: vertical;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  background: #f8fafc;
  color: #0f172a;
  line-height: 1.45;
}
.artifact-edit-field textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

/* Markdown 样式 */
.markdown-body :deep(p) { margin: 0 0 12px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
  margin: 16px 0 8px; font-weight: 600;
}
.markdown-body :deep(h1) { font-size: 1.3em; }
.markdown-body :deep(h2) { font-size: 1.15em; }
.markdown-body :deep(h3) { font-size: 1.05em; }
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(code) {
  background: #f3f4f6; padding: 2px 6px; border-radius: 4px;
  font-size: 0.9em; font-family: 'SF Mono', monospace;
}
.markdown-body :deep(pre) {
  background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 8px;
  overflow-x: auto; margin: 12px 0; font-size: 13px;
}
.markdown-body :deep(pre code) { background: none; padding: 0; color: inherit; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 8px 0; padding-left: 24px; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(a) { color: #2563eb; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }
.markdown-body :deep(.app-link) { color: #2563eb; cursor: pointer; font-weight: 500; }
.markdown-body :deep(.app-link:hover) { text-decoration: underline; }

.markdown-body :deep(.entity-link-card) {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 440px;
  margin: 10px 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  color: inherit;
  text-decoration: none;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}
.markdown-body :deep(.entity-link-card:hover) {
  transform: translateY(-1px);
  border-color: #bfdbfe;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.10);
  text-decoration: none;
}
.markdown-body :deep(.entity-icon) {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
}
.markdown-body :deep(.entity-order .entity-icon) { background: #2563eb; }
.markdown-body :deep(.entity-content .entity-icon) { background: #059669; }
.markdown-body :deep(.entity-main) {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.markdown-body :deep(.entity-title) {
  color: #111827;
  font-size: 14px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.markdown-body :deep(.entity-subtitle) {
  color: #64748b;
  font-size: 12px;
}
.markdown-body :deep(.entity-action) {
  flex: 0 0 auto;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}
.markdown-body :deep(.entity-content .entity-action) { color: #047857; }

.markdown-body :deep(.execution-result-card) {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 560px;
  margin: 12px 0;
  padding: 13px 14px;
  border: 1px solid #bbf7d0;
  border-radius: 14px;
  background: linear-gradient(135deg, #f0fdf4 0%, #eff6ff 100%);
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.08);
  color: #0f172a;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.markdown-body :deep(.execution-result-card:hover) {
  transform: translateY(-1px);
  border-color: #86efac;
  background: linear-gradient(135deg, #ecfdf5 0%, #e0f2fe 100%);
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
}
.markdown-body :deep(.execution-icon) {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 13px;
  background: #2563eb;
  color: #ffffff;
  font-size: 15px;
  font-weight: 900;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18);
}
.markdown-body :deep(.execution-content .execution-icon) {
  background: #059669;
  box-shadow: 0 10px 20px rgba(5, 150, 105, 0.18);
}
.markdown-body :deep(.execution-comment .execution-icon) {
  background: #d97706;
  box-shadow: 0 10px 20px rgba(217, 119, 6, 0.18);
}
.markdown-body :deep(.execution-like .execution-icon) {
  background: #e11d48;
  box-shadow: 0 10px 20px rgba(225, 29, 72, 0.18);
}
.markdown-body :deep(.execution-main) {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.markdown-body :deep(.execution-title) {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.35;
}
.markdown-body :deep(.execution-subtitle) {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}
.markdown-body :deep(.execution-action) {
  flex: 0 0 auto;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  color: #1d4ed8;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.markdown-body :deep(.execution-action:hover) {
  border-color: #93c5fd;
  background: #dbeafe;
  color: #1e40af;
  text-decoration: none;
}

@media (max-width: 640px) {
  .markdown-body :deep(.execution-result-card) {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .markdown-body :deep(.execution-main) {
    flex: 1 1 calc(100% - 54px);
  }

  .markdown-body :deep(.execution-action) {
    margin-left: 54px;
  }
}

/* 地图 */
/* 状态文字 */
.status-text { font-size: 13px; color: #9ca3af; padding: 4px 0; }

/* 回复后的下一步建议 */
.reply-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #edf2f7;
}
.reply-action {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.15s;
}
.reply-action span {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}
.reply-action:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  transform: translateY(-1px);
}
.reply-action:disabled {
  cursor: default;
  opacity: 0.55;
}

/* 地图卡片 */
.markdown-body :deep(.map-card) {
  margin: 14px 0;
  max-width: 560px;
  overflow: hidden;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
}
.markdown-body :deep(.map-tile-stage) {
  position: relative;
  height: 220px;
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
  z-index: 2;
  color: #ef4444;
  transform: translate(-50%, -100%);
  filter: drop-shadow(0 4px 8px rgba(127, 29, 29, 0.35));
}
.markdown-body :deep(.map-badge) {
  position: absolute;
  left: 12px;
  top: 12px;
  z-index: 2;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}
.markdown-body :deep(.map-card-meta) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 14px;
}
.markdown-body :deep(.map-card-info) { min-width: 0; }
.markdown-body :deep(.map-card-title) { font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 4px; }
.markdown-body :deep(.map-card-coords) { font-size: 12px; color: #64748b; font-family: monospace; }
.markdown-body :deep(.map-card-actions) {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.markdown-body :deep(.map-card-action) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 8px 11px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  font-family: inherit;
}
.markdown-body :deep(.map-card-action:hover) { background: #dbeafe; text-decoration: none; }
.markdown-body :deep(.map-card-draft) {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}
.markdown-body :deep(.map-card-draft:hover) {
  background: #1d4ed8;
  color: #ffffff;
  border-color: #1d4ed8;
}
.markdown-body :deep(.map-tile-stage) {
  cursor: grab;
  user-select: none;
  touch-action: none;
}
.markdown-body :deep(.map-tile-stage.dragging) { cursor: grabbing; }
.markdown-body :deep(.map-controls) {
  position: absolute;
  right: 12px;
  top: 12px;
  z-index: 3;
  display: grid;
  grid-template-columns: repeat(2, 32px);
  gap: 6px;
}
.markdown-body :deep(.map-control) {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.92);
  color: #1e293b;
  cursor: pointer;
  font-size: 15px;
  font-weight: 800;
  line-height: 1;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
}
.markdown-body :deep(.map-control:hover) {
  background: #eff6ff;
  color: #1d4ed8;
}
.markdown-body :deep(.map-card-hint) {
  padding: 0 14px 12px;
  color: #64748b;
  font-size: 12px;
}

/* ==================== 输入区域 ==================== */
.input-area {
  padding: 12px 16px 16px;
  max-width: 768px; width: 100%; margin: 0 auto;
}
.input-wrapper {
  display: flex; align-items: flex-end; gap: 8px;
  border: 1px solid #d1d5db; border-radius: 16px;
  padding: 8px 8px 8px 16px; background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-wrapper:focus-within {
  border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.1);
}
.input-wrapper textarea {
  flex: 1; border: none; outline: none; resize: none;
  font-size: 15px; line-height: 1.5; font-family: inherit;
  max-height: 200px; min-height: 24px; padding: 4px 0;
  background: transparent; color: #111;
}
.input-wrapper textarea::placeholder { color: #9ca3af; }
.input-wrapper textarea:disabled { opacity: 0.5; }

.btn-send {
  flex-shrink: 0; width: 36px; height: 36px; border: none;
  border-radius: 50%; background: #e5e7eb; color: #9ca3af;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.btn-send svg { width: 18px; height: 18px; }
.btn-send.active { background: #2563eb; color: #fff; }
.btn-send.active:hover { background: #1d4ed8; }
.btn-send:disabled { cursor: default; opacity: 0.5; }

.input-hint {
  text-align: center; font-size: 12px; color: #9ca3af;
  margin-top: 8px;
}

/* ==================== 记忆面板 ==================== */
.memory-panel {
  display: grid;
  gap: 10px;
  padding: 2px 2px 14px;
}
.memory-empty {
  text-align: center;
  color: #64748b;
  padding: 36px 16px;
  border: 1px dashed #d8e0ec;
  border-radius: 10px;
  background: #f8fafc;
}
.memory-item {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #e4ebf5;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
}
.memory-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}
.memory-tag {
  max-width: calc(100% - 38px);
  overflow: hidden;
  text-overflow: ellipsis;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.4;
  padding: 3px 9px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  white-space: nowrap;
}
.memory-content {
  min-width: 0;
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.memory-delete {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
  transition: all 0.15s;
}
.memory-delete:hover {
  color: #ef4444;
  background: #fef2f2;
  border-color: #fecaca;
}

/* ==================== 暗色模式 ==================== */
:global(:root[data-theme='dark']) .ai-view,
:global(:root[data-theme='dark']) .chat-main {
  background: #101722;
}

:global(:root[data-theme='dark']) .sidebar {
  background: #0b1320;
  color: #e5edf8;
  border-right-color: rgba(148, 163, 184, 0.18);
}

:global(:root[data-theme='dark']) .btn-new-chat,
:global(:root[data-theme='dark']) .btn-expand,
:global(:root[data-theme='dark']) .btn-start,
:global(:root[data-theme='dark']) .prompt-card,
:global(:root[data-theme='dark']) .quick-prompt,
:global(:root[data-theme='dark']) .input-wrapper {
  background: #172235;
  color: #e5edf8;
  border-color: rgba(148, 163, 184, 0.22);
}

:global(:root[data-theme='dark']) .btn-new-chat:hover,
:global(:root[data-theme='dark']) .conv-item:hover,
:global(:root[data-theme='dark']) .btn-memory:hover,
:global(:root[data-theme='dark']) .btn-toggle:hover,
:global(:root[data-theme='dark']) .btn-start:hover,
:global(:root[data-theme='dark']) .prompt-card:hover,
:global(:root[data-theme='dark']) .quick-prompt:hover {
  background: #1f2d44;
  color: #f8fbff;
  border-color: rgba(148, 163, 184, 0.28);
}

:global(:root[data-theme='dark']) .conv-item {
  color: #aebbd0;
}

:global(:root[data-theme='dark']) .conv-item.active {
  background: #24334d;
  color: #f8fbff;
}

:global(:root[data-theme='dark']) .sidebar-footer {
  border-top-color: rgba(148, 163, 184, 0.18);
}

:global(:root[data-theme='dark']) .btn-memory,
:global(:root[data-theme='dark']) .btn-toggle,
:global(:root[data-theme='dark']) .empty-state,
:global(:root[data-theme='dark']) .empty-subtitle,
:global(:root[data-theme='dark']) .operation-detail,
:global(:root[data-theme='dark']) .artifact-description {
  color: #94a3b8;
}

:global(:root[data-theme='dark']) .empty-title,
:global(:root[data-theme='dark']) .assistant-content,
:global(:root[data-theme='dark']) .operation-title,
:global(:root[data-theme='dark']) .prompt-main strong {
  color: #edf4ff;
}

:global(:root[data-theme='dark']) .prompt-main small {
  color: #94a3b8;
}

:global(:root[data-theme='dark']) .prompt-icon {
  background: #223554;
  color: #bfdbfe;
}

:global(:root[data-theme='dark']) .assistant-avatar {
  background: #162235;
  border-color: rgba(148, 163, 184, 0.22);
  color: #9ab8ff;
}

:global(:root[data-theme='dark']) .operation-timeline,
:global(:root[data-theme='dark']) .artifact-card,
:global(:root[data-theme='dark']) .markdown-body :deep(.entity-link-card),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-result-card),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-card) {
  background: #172235;
  border-color: rgba(148, 163, 184, 0.22);
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.24);
}

:global(:root[data-theme='dark']) .operation-summary-head {
  color: #c7d8f4;
  border-bottom-color: rgba(148, 163, 184, 0.16);
}

:global(:root[data-theme='dark']) .artifact-confirmation {
  background: linear-gradient(180deg, #172235 0%, #132033 100%);
  border-color: rgba(91, 140, 255, 0.34);
}

:global(:root[data-theme='dark']) .artifact-guide {
  background: linear-gradient(180deg, #172235 0%, #102534 100%);
  border-color: rgba(45, 212, 191, 0.28);
}

:global(:root[data-theme='dark']) .artifact-guide .artifact-icon {
  background: #0f766e;
  color: #ccfbf1;
}

:global(:root[data-theme='dark']) .artifact-title,
:global(:root[data-theme='dark']) .artifact-field-value,
:global(:root[data-theme='dark']) .markdown-body :deep(.entity-title),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-title),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-title),
:global(:root[data-theme='dark']) .memory-content {
  color: #edf4ff;
}

:global(:root[data-theme='dark']) .artifact-field,
:global(:root[data-theme='dark']) .artifact-edit-field textarea {
  background: #101a2a;
  border-color: rgba(148, 163, 184, 0.22);
  color: #edf4ff;
}

:global(:root[data-theme='dark']) .artifact-field.missing {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.35);
}

:global(:root[data-theme='dark']) .artifact-field-label,
:global(:root[data-theme='dark']) .artifact-edit-field,
:global(:root[data-theme='dark']) .markdown-body :deep(.entity-subtitle),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-subtitle),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-coords),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-hint) {
  color: #94a3b8;
}

:global(:root[data-theme='dark']) .artifact-action {
  background: #101a2a;
  color: #dbe7f8;
  border-color: rgba(148, 163, 184, 0.28);
}

:global(:root[data-theme='dark']) .artifact-prompt-actions {
  border-top-color: rgba(148, 163, 184, 0.16);
}

:global(:root[data-theme='dark']) .artifact-action:hover:not(:disabled),
:global(:root[data-theme='dark']) .markdown-body :deep(.entity-link-card:hover),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-result-card:hover) {
  background: #1f2d44;
  border-color: rgba(154, 184, 255, 0.38);
  color: #f8fbff;
}

:global(:root[data-theme='dark']) .artifact-action.primary {
  background: #3768d8;
  border-color: #5b8cff;
  color: #ffffff;
}

:global(:root[data-theme='dark']) .artifact-action.primary:hover:not(:disabled) {
  background: #4c7df0;
  border-color: #9ab8ff;
}

:global(:root[data-theme='dark']) .artifact-action.ghost:hover:not(:disabled) {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.32);
  color: #fbbf24;
}

:global(:root[data-theme='dark']) .reply-actions {
  border-top-color: rgba(148, 163, 184, 0.16);
}

:global(:root[data-theme='dark']) .reply-action {
  background: #172235;
  color: #dbe7f8;
  border-color: rgba(148, 163, 184, 0.24);
}

:global(:root[data-theme='dark']) .reply-action span {
  background: #223554;
  color: #bfdbfe;
}

:global(:root[data-theme='dark']) .reply-action:hover:not(:disabled) {
  background: #1f2d44;
  color: #f8fbff;
  border-color: rgba(154, 184, 255, 0.38);
}

:global(:root[data-theme='dark']) .markdown-body :deep(code) {
  background: #101a2a;
  color: #bfdbfe;
}

:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-action),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-action),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-control),
:global(:root[data-theme='dark']) .memory-tag {
  background: #223554;
  color: #bfdbfe;
  border-color: rgba(148, 163, 184, 0.24);
}

:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-action:hover),
:global(:root[data-theme='dark']) .markdown-body :deep(.execution-action:hover),
:global(:root[data-theme='dark']) .markdown-body :deep(.map-control:hover) {
  background: #2d4470;
  color: #f8fbff;
  text-decoration: none;
}

:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-draft) {
  background: #3768d8;
  color: #ffffff;
  border-color: #5b8cff;
}

:global(:root[data-theme='dark']) .markdown-body :deep(.map-card-draft:hover) {
  background: #4c7df0;
  color: #ffffff;
  border-color: #9ab8ff;
}

:global(:root[data-theme='dark']) .markdown-body :deep(.map-badge) {
  background: rgba(15, 23, 42, 0.86);
  color: #bfdbfe;
}

:global(:root[data-theme='dark']) .input-wrapper textarea {
  color: #edf4ff;
}

:global(:root[data-theme='dark']) .memory-item {
  background: #172235;
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
}

:global(:root[data-theme='dark']) .memory-empty {
  background: #172235;
  border-color: rgba(148, 163, 184, 0.22);
  color: #94a3b8;
}

:global(:root[data-theme='dark']) .memory-delete {
  color: #94a3b8;
  border-color: rgba(148, 163, 184, 0.12);
}

:global(:root[data-theme='dark']) .memory-delete:hover {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(248, 113, 113, 0.28);
}

:global(:root[data-theme='dark']) :deep(.memory-drawer),
:global(:root[data-theme='dark']) :deep(.el-drawer) {
  background: #101722;
  color: #edf4ff;
}

:global(:root[data-theme='dark']) :deep(.el-drawer__header) {
  color: #edf4ff;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  margin-bottom: 12px;
}

:global(:root[data-theme='dark']) :deep(.el-drawer__body) {
  background: #101722;
}

/* v-html 注入的卡片不会携带 scoped attribute，暗色覆盖必须用纯全局选择器。 */
:global(html[data-theme='dark'] .markdown-body .entity-link-card),
:global(html[data-theme='dark'] .markdown-body .execution-result-card),
:global(html[data-theme='dark'] .markdown-body .map-card) {
  background: #172235 !important;
  color: #edf4ff !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.24) !important;
}

:global(html[data-theme='dark'] .markdown-body .entity-link-card:hover),
:global(html[data-theme='dark'] .markdown-body .execution-result-card:hover) {
  background: #1f2d44 !important;
  border-color: rgba(154, 184, 255, 0.38) !important;
}

:global(html[data-theme='dark'] .markdown-body .entity-title),
:global(html[data-theme='dark'] .markdown-body .execution-title),
:global(html[data-theme='dark'] .markdown-body .map-card-title) {
  color: #edf4ff !important;
}

:global(html[data-theme='dark'] .markdown-body .entity-subtitle),
:global(html[data-theme='dark'] .markdown-body .execution-subtitle),
:global(html[data-theme='dark'] .markdown-body .map-card-coords),
:global(html[data-theme='dark'] .markdown-body .map-card-hint) {
  color: #94a3b8 !important;
}

:global(html[data-theme='dark'] .markdown-body .map-card-action),
:global(html[data-theme='dark'] .markdown-body .execution-action),
:global(html[data-theme='dark'] .markdown-body .map-control) {
  background: #223554 !important;
  color: #bfdbfe !important;
  border-color: rgba(148, 163, 184, 0.24) !important;
}

:global(html[data-theme='dark'] .markdown-body .map-card-action:hover),
:global(html[data-theme='dark'] .markdown-body .execution-action:hover),
:global(html[data-theme='dark'] .markdown-body .map-control:hover) {
  background: #2d4470 !important;
  color: #f8fbff !important;
  text-decoration: none !important;
}

:global(html[data-theme='dark'] .markdown-body .map-card-draft) {
  background: #3768d8 !important;
  color: #ffffff !important;
  border-color: #5b8cff !important;
}

:global(html[data-theme='dark'] .markdown-body .map-card-draft:hover) {
  background: #4c7df0 !important;
  color: #ffffff !important;
  border-color: #9ab8ff !important;
}

:global(html[data-theme='dark'] .markdown-body .map-badge) {
  background: rgba(15, 23, 42, 0.86) !important;
  color: #bfdbfe !important;
}

:global(html[data-theme='dark'] .ai-view .btn-new-chat),
:global(html[data-theme='dark'] .ai-view .btn-memory),
:global(html[data-theme='dark'] .ai-view .btn-toggle),
:global(html[data-theme='dark'] .ai-view .btn-start) {
  background: #182333 !important;
  color: #edf4ff !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
}

:global(html[data-theme='dark'] .ai-view .btn-new-chat:hover),
:global(html[data-theme='dark'] .ai-view .btn-memory:hover),
:global(html[data-theme='dark'] .ai-view .btn-toggle:hover),
:global(html[data-theme='dark'] .ai-view .btn-start:hover),
:global(html[data-theme='dark'] .ai-view .conv-item:hover) {
  background: #1f2d44 !important;
  color: #f8fbff !important;
  border-color: rgba(154, 184, 255, 0.38) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-edit-field textarea),
:global(html[data-theme='dark'] .ai-view .artifact-edit-input) {
  background: #101a2a !important;
  color: #edf4ff !important;
  border-color: rgba(148, 163, 184, 0.28) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-card) {
  background: #172235 !important;
  background-image: none !important;
  color: #edf4ff !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.24) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-field) {
  background: #101a2a !important;
  border-color: rgba(148, 163, 184, 0.24) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-field.missing) {
  background: rgba(245, 158, 11, 0.12) !important;
  border-color: rgba(245, 158, 11, 0.34) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-field-label) {
  color: #94a3b8 !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-field-value) {
  color: #edf4ff !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-action) {
  background: #101a2a !important;
  color: #dbe7f8 !important;
  border-color: rgba(148, 163, 184, 0.28) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-action:hover:not(:disabled)) {
  background: #1f2d44 !important;
  color: #f8fbff !important;
  border-color: rgba(154, 184, 255, 0.38) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-action.primary) {
  background: #3768d8 !important;
  color: #ffffff !important;
  border-color: #5b8cff !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-action.primary:hover:not(:disabled)) {
  background: #4c7df0 !important;
  border-color: #9ab8ff !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-action.ghost:hover:not(:disabled)) {
  background: rgba(245, 158, 11, 0.12) !important;
  color: #fbbf24 !important;
  border-color: rgba(245, 158, 11, 0.32) !important;
}

:global(html[data-theme='dark'] .ai-view .reply-actions) {
  border-top-color: rgba(148, 163, 184, 0.16) !important;
}

:global(html[data-theme='dark'] .ai-view .reply-action) {
  background: #172235 !important;
  color: #dbe7f8 !important;
  border-color: rgba(148, 163, 184, 0.24) !important;
}

:global(html[data-theme='dark'] .ai-view .reply-action span) {
  background: #223554 !important;
  color: #bfdbfe !important;
}

:global(html[data-theme='dark'] .ai-view .reply-action:hover:not(:disabled)) {
  background: #1f2d44 !important;
  color: #f8fbff !important;
  border-color: rgba(154, 184, 255, 0.38) !important;
}

:global(html[data-theme='dark'] .ai-view .artifact-confirmation) {
  background: linear-gradient(180deg, #172235 0%, #132033 100%) !important;
  border-color: rgba(91, 140, 255, 0.34) !important;
}

:global(html[data-theme='dark'] .ai-view .operation-timeline) {
  background: #172235 !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.24) !important;
}

:global(html[data-theme='dark'] .ai-view .operation-summary-head) {
  color: #c7d8f4 !important;
  border-bottom-color: rgba(148, 163, 184, 0.16) !important;
}

:global(html[data-theme='dark'] .memory-drawer) {
  background: #101722 !important;
  color: #edf4ff !important;
}

:global(html[data-theme='dark'] .memory-drawer .el-drawer__header) {
  color: #edf4ff !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18) !important;
  margin-bottom: 12px !important;
}

:global(html[data-theme='dark'] .memory-drawer .el-drawer__body) {
  background: #101722 !important;
}

:global(html[data-theme='dark'] .memory-drawer .memory-empty),
:global(html[data-theme='dark'] .memory-drawer .memory-item) {
  background: #172235 !important;
  color: #edf4ff !important;
  border-color: rgba(148, 163, 184, 0.22) !important;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18) !important;
}

:global(html[data-theme='dark'] .memory-drawer .memory-content) {
  color: #edf4ff !important;
}

:global(html[data-theme='dark'] .memory-drawer .memory-tag) {
  background: #223554 !important;
  color: #bfdbfe !important;
  border-color: rgba(148, 163, 184, 0.24) !important;
}

:global(html[data-theme='dark'] .memory-drawer .memory-delete) {
  color: #94a3b8 !important;
  border-color: rgba(148, 163, 184, 0.12) !important;
}

:global(html[data-theme='dark'] .memory-drawer .memory-delete:hover) {
  color: #fca5a5 !important;
  background: rgba(239, 68, 68, 0.12) !important;
  border-color: rgba(248, 113, 113, 0.28) !important;
}

:global(html[data-theme='dark'] .ai-view .operation-step + .operation-step) {
  border-top-color: rgba(148, 163, 184, 0.16) !important;
}

:global(html[data-theme='dark'] .ai-view .operation-title) {
  color: #edf4ff !important;
}

:global(html[data-theme='dark'] .ai-view .operation-detail) {
  color: #94a3b8 !important;
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .ai-layout {
    position: relative;
  }

  .sidebar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(78vw, 280px);
    min-width: 0;
    z-index: 20;
    box-shadow: 12px 0 30px rgba(15, 23, 42, 0.16);
  }

  .sidebar.collapsed { width: 0; }
  .chat-main { width: 100%; }
  .btn-expand { position: absolute; top: 12px; left: 12px; }
  .user-message-text { max-width: 85%; }
  .messages-inner { padding: 16px 12px; }
  .input-area { padding: 12px; }
  .empty-state { justify-content: flex-start; padding-top: 44px; }
  .prompt-gallery { grid-template-columns: 1fr; }
  .prompt-card { min-height: 74px; }
  .quick-prompts { max-width: 100%; }
}
</style>
