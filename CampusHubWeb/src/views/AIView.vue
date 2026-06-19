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
          <button class="btn-start" @click="handleNewConversation">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
            开始新对话
          </button>
        </section>

        <!-- 对话区域 -->
        <section v-else class="chat-area">
          <div class="messages-container" ref="chatContainer" @click="handleChatClick">
            <div v-if="messages.length === 0" class="chat-empty-state">
              <div class="chat-empty-icon">
                <svg viewBox="0 0 24 24" width="30" height="30"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z" fill="currentColor"/></svg>
              </div>
              <h3>新的对话</h3>
              <p>输入活动、天气、地点或校园服务问题，CampusHub 会帮你继续查找。</p>
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
                      <div v-if="message.operations?.length" class="operation-timeline">
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
                          <div v-if="artifact.fields?.length" class="artifact-fields">
                            <div
                              v-for="(field, fieldIndex) in artifact.fields"
                              :key="fieldIndex"
                              :class="['artifact-field', { missing: field.missing }]"
                            >
                              <span class="artifact-field-label">{{ field.label }}</span>
                              <span class="artifact-field-value">{{ formatArtifactValue(field.value) }}</span>
                            </div>
                          </div>
                          <div v-if="artifact.type === 'confirmation'" class="artifact-actions">
                            <button class="artifact-action primary" :disabled="sending" @click="handleArtifactAction(artifact, 'confirm')">
                              确认执行
                            </button>
                            <button class="artifact-action" :disabled="sending" @click="handleArtifactAction(artifact, 'edit')">
                              修改草稿
                            </button>
                            <button class="artifact-action ghost" :disabled="sending" @click="handleArtifactAction(artifact, 'cancel')">
                              取消
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
    <el-drawer v-model="showMemoryPanel" title="AI 对你的了解" direction="rtl" size="380px">
      <div class="memory-panel">
        <div v-if="memories.length === 0" class="memory-empty">AI 还没有记住关于你的任何信息</div>
        <div v-for="mem in memories" :key="mem.memId" class="memory-item">
          <div class="memory-tag">{{ mem.category }}</div>
          <div class="memory-content">{{ mem.content }}</div>
          <button class="memory-delete" @click="handleDeleteMemory(mem.memId)" title="删除此记忆">
            <svg viewBox="0 0 24 24" width="14" height="14"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
          </button>
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
  return {
    ...payload,
    type,
    fields: fields.map(field => {
      if (field && typeof field === 'object') return field
      return { label: '信息', value: field }
    })
  }
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

async function sendMessageText(text) {
  if (!text || sending.value) return
  inputMessage.value = text
  await nextTick()
  await handleSendMessage()
}

function handleArtifactAction(artifact, action) {
  const title = artifact?.title || '这个草稿'
  const messages = {
    confirm: artifact?.confirmMessage || `我确认执行这个草稿：${title}`,
    edit: artifact?.editMessage || `我想修改这个草稿：${title}`,
    cancel: artifact?.cancelMessage || `取消这个草稿：${title}`
  }
  sendMessageText(messages[action])
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

async function switchConversation(cid) {
  currentConvId.value = cid
  messages.value = []
  try {
    const resp = await agentService.getMessages(cid)
    const rawMessages = resp.data?.data || []
    messages.value = rawMessages.map(m => ({ ...m, loading: false }))
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
  scrollToBottom()

  sending.value = true
  let doneReceived = false

  agentService.streamMessage(currentConvId.value, msgText, {
    onDelta(text) {
      if (aiMsg.loading) aiMsg.loading = false
      if (aiMsg.status) aiMsg.status = ''  // 收到实际内容后清除 status
      aiMsg.content += text
      scrollToBottom()
    },
    onStatus(statusText) {
      if (aiMsg.loading) aiMsg.loading = false
      applyAgentEvent(aiMsg, 'status', statusText)
      scrollToBottom()
    },
    onEvent(eventName, data) {
      if (aiMsg.loading) aiMsg.loading = false
      applyAgentEvent(aiMsg, eventName, data)
      scrollToBottom()
    },
    async onDone() {
      if (doneReceived) return
      doneReceived = true
      aiMsg.loading = false
      if (!aiMsg.content) aiMsg.content = '抱歉，AI 未返回有效内容。'
      sending.value = false
      scrollToBottom()
      await loadConversations()
    },
    onError(errMsg) {
      aiMsg.loading = false
      aiMsg.content = `错误：${errMsg}`
      sending.value = false
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

const renderMarkdown = (md) => {
  if (!md) return ''

  const mapBlocks = []
  md = md.replace(/:::map\{([^}]+)\}/g, (match, attrs) => {
    const idx = mapBlocks.length
    const props = {}
    attrs.replace(/(\w+)=([^\s}]+)/g, (m, k, v) => { props[k] = v.replace(/^["']|["']$/g, '') })
    mapBlocks.push(props)
    return `@@MAP_BLOCK_${idx}@@`
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

  const parts = md.split(/\n\s*\n/)
  md = parts.map(p => {
    const s = p.replace(/\n/g, '<br/>')
    return /^<(h\d|ul|ol|pre|blockquote|div)/.test(s) ? s : ('<p>' + s + '</p>')
  }).join('\n')

  md = md.replace(/@@CODE_BLOCK_(\d+)@@/g, (m, idx) => {
    const code = codeBlocks[Number(idx)] || ''
    return '<pre><code>' + escapeHtml(code) + '</code></pre>'
  })

  md = md.replace(/@@MAP_BLOCK_(\d+)@@/g, (m, idx) => {
    const p = mapBlocks[Number(idx)]
    if (!p || !p.lng || !p.lat) return ''
    const title = p.title || '位置'
    const amapLink = `https://uri.amap.com/marker?position=${p.lng},${p.lat}&name=${encodeURIComponent(title)}`
    return `<div class="map-card">` +
      `<a href="${amapLink}" target="_blank" rel="noopener noreferrer" class="map-card-inner">` +
        `<div class="map-card-icon"><svg viewBox="0 0 24 24" width="32" height="32"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="#2563eb"/></svg></div>` +
        `<div class="map-card-info">` +
          `<div class="map-card-title">${escapeHtml(title)}</div>` +
          `<div class="map-card-coords">${p.lng}, ${p.lat}</div>` +
          `<div class="map-card-action">点击在高德地图中查看</div>` +
        `</div>` +
        `<div class="map-card-arrow"><svg viewBox="0 0 24 24" width="20" height="20"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z" fill="#9ca3af"/></svg></div>` +
      `</a>` +
    `</div>`
  })

  return md
}

const formatContent = (text) => {
  if (!text) return ''
  let cleaned = text
  // 清除可能混入的 status 前缀（历史数据兼容）
  cleaned = cleaned.replace(/^正在思考\.{0,3}/g, '')
  // 如果文本中有不完整的 :::map{ 语法（流式拼接中），显示加载提示
  cleaned = cleaned.replace(/:::map\{[^}]*$/g, '<p style="color:#9ca3af">正在加载地图...</p>')
  return renderMarkdown(cleaned.trim())
}

function handleChatClick(e) {
  const link = e.target.closest('.app-link')
  if (link) {
    e.preventDefault()
    const route = link.dataset.route
    if (route) router.push(route)
  }
}

// ==================== 生命周期 ====================

onMounted(async () => {
  syncSidebarForViewport()
  window.addEventListener('resize', syncSidebarForViewport)
  await loadConversations()
  if (conversations.value.length > 0) {
    await switchConversation(conversations.value[0].cid)
  }
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', syncSidebarForViewport)
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
  justify-content: center; gap: 12px; color: #6b7280;
}
.empty-logo { opacity: 0.4; }
.empty-title { margin: 0; font-size: 22px; font-weight: 600; color: #111; }
.empty-subtitle { margin: 0; font-size: 14px; color: #9ca3af; }
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
.operation-step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 6px 0;
  color: #64748b;
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
.artifact-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
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

/* 地图 */
/* 状态文字 */
.status-text { font-size: 13px; color: #9ca3af; padding: 4px 0; }

/* 地图卡片 */
.markdown-body :deep(.map-card) { margin: 12px 0; max-width: 420px; }
.markdown-body :deep(.map-card-inner) {
  display: flex; align-items: center; gap: 12px; padding: 14px 16px;
  border: 1px solid #e5e7eb; border-radius: 12px; background: #f9fafb;
  text-decoration: none; color: inherit; transition: all 0.15s;
}
.markdown-body :deep(.map-card-inner:hover) { background: #eff6ff; border-color: #bfdbfe; }
.markdown-body :deep(.map-card-icon) { flex-shrink: 0; }
.markdown-body :deep(.map-card-info) { flex: 1; min-width: 0; }
.markdown-body :deep(.map-card-title) { font-size: 14px; font-weight: 600; color: #111827; margin-bottom: 2px; }
.markdown-body :deep(.map-card-coords) { font-size: 12px; color: #9ca3af; font-family: monospace; }
.markdown-body :deep(.map-card-action) { font-size: 12px; color: #2563eb; margin-top: 4px; }
.markdown-body :deep(.map-card-arrow) { flex-shrink: 0; color: #9ca3af; }

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
.memory-panel { padding: 0 4px; }
.memory-empty { text-align: center; color: #999; padding: 32px 0; }
.memory-item { display: flex; align-items: flex-start; gap: 8px; padding: 12px; border-bottom: 1px solid #f0f0f0; }
.memory-tag { background: #eff6ff; color: #2563eb; font-size: 11px; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.memory-content { flex: 1; font-size: 13px; color: #333; line-height: 1.5; }
.memory-delete { border: none; background: transparent; color: #ccc; cursor: pointer; padding: 2px; flex-shrink: 0; }
.memory-delete:hover { color: #ef4444; }

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
}
</style>
