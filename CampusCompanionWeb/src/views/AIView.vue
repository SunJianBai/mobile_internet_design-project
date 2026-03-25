<template>
  <div class="ai-view">
    <div class="ai-layout">
      <!-- 左侧：会话列表 -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <h3>对话记录</h3>
          <button class="btn-icon" @click="handleNewConversation" title="新建对话">
            <svg viewBox="0 0 24 24" width="18" height="18"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
          </button>
        </div>
        <div class="conversation-list">
          <div
            v-for="conv in conversations"
            :key="conv.cid"
            :class="['conv-item', { active: currentConvId === conv.cid }]"
            @click="switchConversation(conv.cid)"
          >
            <span class="conv-title">{{ conv.title }}</span>
            <button class="btn-delete" @click.stop="handleDeleteConversation(conv.cid)" title="删除">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/></svg>
            </button>
          </div>
          <div v-if="conversations.length === 0" class="empty-hint">暂无对话，点击上方 + 新建</div>
        </div>

        <!-- 记忆管理入口 -->
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

      <!-- 移动端：展开侧边栏按钮 -->
      <button v-if="sidebarCollapsed" class="btn-expand" @click="sidebarCollapsed = false">
        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="currentColor"/></svg>
      </button>

      <!-- 右侧：聊天主区域 -->
      <main class="chat-main">
        <section v-if="!currentConvId" class="empty-state">
          <div class="empty-icon">
            <svg viewBox="0 0 24 24" width="64" height="64"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="#ddd"/></svg>
          </div>
          <p>选择一个对话或新建对话开始</p>
          <el-button type="primary" @click="handleNewConversation">
            <svg viewBox="0 0 24 24" width="16" height="16" style="margin-right:6px"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/></svg>
            新建对话
          </el-button>
        </section>

        <section v-else class="ai-chat-card">
          <div class="chat-messages" ref="chatContainer">
            <div v-for="message in messages" :key="message.mid" :class="['message-row', message.role]">
              <!-- 隐藏 tool 类型消息 -->
              <template v-if="message.role !== 'tool'">
                <div class="avatar">
                  <el-avatar :src="message.role === 'user' ? userAvatar : aiAvatar" :size="32" />
                </div>
                <div class="bubble">
                  <div class="bubble-content">
                    <div v-if="message.role === 'assistant' && message.loading" class="loading-indicator">
                      <div class="three-body" aria-hidden="true" title="AI 正在生成回复">
                        <div class="three-body__dot"></div>
                        <div class="three-body__dot"></div>
                        <div class="three-body__dot"></div>
                      </div>
                    </div>
                    <div v-else v-html="formatContent(message.content)"></div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <div class="chat-input-area">
            <div class="input-box">
              <el-input
                ref="inputRef"
                v-model="inputMessage"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 10 }"
                placeholder="请输入你的问题，Shift+Enter 换行，Enter 发送"
                @input="saveDraft"
                maxlength="4000"
              />
            </div>
            <div class="controls">
              <div class="meta">
                <span class="char-count">{{ inputLength }} / 4000</span>
              </div>
              <div class="actions">
                <button class="btn clear" @click="handleClear" title="清空对话">清空</button>
                <button
                  class="btn send"
                  :class="{ sending: sending }"
                  @click="handleSendMessage"
                  :disabled="sending || !inputMessage.trim()"
                  title="发送 (Enter)"
                >
                  <svg viewBox="0 0 24 24" width="18" height="18" class="send-icon">
                    <path d="M12 2L3 21h7l2-6 2 6h7L12 2z" fill="currentColor" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>

    <!-- 记忆管理面板 -->
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
import { ElMessage, ElMessageBox } from 'element-plus'
import agentService from '../services/agent'

const chatContainer = ref(null)
const inputRef = ref(null)

const conversations = ref([])
const currentConvId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const sidebarCollapsed = ref(false)
const showMemoryPanel = ref(false)
const memories = ref([])

try { inputMessage.value = localStorage.getItem('ai_draft') || '' } catch (e) { /* ignore */ }

const userAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'
const aiAvatar = 'https://cube.elemecdn.com/9/c2/f0ee8a3c7c9638a54940382568c9dpng.png'
const inputLength = computed(() => inputMessage.value.length)

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

  // 如果没有选择会话，自动创建
  if (!currentConvId.value) {
    await handleNewConversation()
    if (!currentConvId.value) return
  }

  const userMsg = {
    mid: Date.now(),
    role: 'user',
    content: inputMessage.value,
    loading: false
  }
  messages.value.push(userMsg)
  const msgText = inputMessage.value
  inputMessage.value = ''
  try { localStorage.removeItem('ai_draft') } catch (e) { /* ignore */ }
  scrollToBottom()

  // placeholder
  const aiMsg = { mid: Date.now() + 1, role: 'assistant', content: '', loading: true }
  messages.value.push(aiMsg)
  scrollToBottom()

  sending.value = true
  let doneReceived = false

  agentService.streamMessage(currentConvId.value, msgText, {
    onDelta(text) {
      if (aiMsg.loading) aiMsg.loading = false
      aiMsg.content += text
      scrollToBottom()
    },
    onStatus(statusText) {
      if (aiMsg.loading) {
        aiMsg.content = statusText
        aiMsg.loading = false
      }
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

function handleClear() {
  if (!currentConvId.value) return
  handleDeleteConversation(currentConvId.value)
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

watch(showMemoryPanel, (val) => {
  if (val) loadMemories()
})

// ==================== 工具函数 ====================

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function saveDraft() {
  try { localStorage.setItem('ai_draft', inputMessage.value) } catch (e) { /* ignore */ }
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      // Shift/Ctrl/Cmd+Enter → 换行（浏览器默认行为）
      return
    }
    e.preventDefault()
    handleSendMessage()
  }
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
  const codeBlocks = []
  md = md.replace(/```([\s\S]*?)```/g, (m, code) => {
    const idx = codeBlocks.length
    codeBlocks.push(code)
    return `@@CODE_BLOCK_${idx}@@`
  })
  md = escapeHtml(md)
  md = md.replace(/^######\s*(.*)$/gm, '<h6>$1</h6>')
  md = md.replace(/^#####\s*(.*)$/gm, '<h5>$1</h5>')
  md = md.replace(/^####\s*(.*)$/gm, '<h4>$1</h4>')
  md = md.replace(/^###\s*(.*)$/gm, '<h3>$1</h3>')
  md = md.replace(/^##\s*(.*)$/gm, '<h2>$1</h2>')
  md = md.replace(/^#\s*(.*)$/gm, '<h1>$1</h1>')
  md = md.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  md = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  md = md.replace(/\*(.+?)\*/g, '<em>$1</em>')
  md = md.replace(/`([^`]+)`/g, '<code>$1</code>')
  md = md.replace(/(^|\n)([ \t]*[-\*]\s+.+)(?=\n|$)/g, (m) => {
    const items = m.split(/\n/).filter(Boolean).map(l => l.replace(/^[ \t]*[-\*]\s+/, ''))
    return '\n<ul>' + items.map(i => '<li>' + i + '</li>').join('') + '</ul>'
  })
  const parts = md.split(/\n\s*\n/)
  md = parts.map(p => {
    const s = p.replace(/\n/g, '<br/>')
    return /^<(h\d|ul|pre|blockquote)/.test(s) ? s : ('<p>' + s + '</p>')
  }).join('\n')
  md = md.replace(/@@CODE_BLOCK_(\d+)@@/g, (m, idx) => {
    const code = codeBlocks[Number(idx)] || ''
    return '<pre><code>' + escapeHtml(code) + '</code></pre>'
  })
  return md
}

const formatContent = (text) => renderMarkdown(text)

// ==================== 生命周期 ====================

onMounted(async () => {
  await loadConversations()
  // 自动选中最近一个会话
  if (conversations.value.length > 0) {
    await switchConversation(conversations.value[0].cid)
  }
  scrollToBottom()
})

onMounted(() => {
  nextTick(() => {
    const ta = inputRef.value?.$el?.querySelector('textarea')
    if (ta) ta.addEventListener('keydown', handleKeydown)
  })
})

onBeforeUnmount(() => {
  const ta = inputRef.value?.$el?.querySelector('textarea')
  if (ta) ta.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.ai-view { width: 100%; height: calc(100vh - 60px); overflow: hidden; }
.ai-layout { display: flex; height: 100%; }

/* ==================== 侧边栏 ==================== */
.sidebar { width: 280px; min-width: 280px; background: #f8f9fb; border-right: 1px solid #e8ecf0; display: flex; flex-direction: column; transition: all 0.2s; }
.sidebar.collapsed { width: 0; min-width: 0; overflow: hidden; border-right: none; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 16px; border-bottom: 1px solid #e8ecf0; }
.sidebar-header h3 { margin: 0; font-size: 15px; font-weight: 600; }
.btn-icon { border: none; background: #409eff; color: #fff; width: 30px; height: 30px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.btn-icon:hover { background: #337ecc; }
.conversation-list { flex: 1; overflow-y: auto; padding: 8px; }
.conv-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px; transition: background 0.15s; }
.conv-item:hover { background: #eef2f7; }
.conv-item.active { background: #e1ecff; }
.conv-title { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-delete { border: none; background: transparent; color: #999; cursor: pointer; padding: 2px; border-radius: 4px; display: flex; opacity: 0; transition: opacity 0.15s; }
.conv-item:hover .btn-delete { opacity: 1; }
.btn-delete:hover { color: #f56c6c; background: rgba(245,108,108,0.1); }
.empty-hint { text-align: center; color: #999; font-size: 13px; padding: 24px 0; }
.sidebar-footer { padding: 12px; border-top: 1px solid #e8ecf0; display: flex; gap: 8px; align-items: center; }
.btn-memory { border: none; background: transparent; color: #606266; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 4px; padding: 6px 10px; border-radius: 6px; flex: 1; }
.btn-memory:hover { background: #eef2f7; }
.btn-toggle { border: none; background: transparent; color: #999; cursor: pointer; padding: 4px; border-radius: 4px; display: flex; }
.btn-toggle:hover { background: #eef2f7; }
.btn-expand { position: fixed; top: 80px; left: 8px; z-index: 10; border: 1px solid #e0e0e0; background: #fff; padding: 8px; border-radius: 8px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }

/* ==================== 聊天主区域 ==================== */
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; color: #999; }
.ai-chat-card { flex: 1; display: flex; flex-direction: column; padding: 16px; overflow: hidden; }
.chat-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
.message-row { display: flex; gap: 12px; align-items: flex-start; }
.message-row.user { flex-direction: row-reverse; }
.avatar { flex: 0 0 36px; }
.bubble { max-width: clamp(300px, 65%, 800px); }
.bubble-content { padding: 12px 14px; border-radius: 12px; line-height: 1.6; word-break: break-word; }
.message-row.user .bubble-content { background: #409eff; color: #fff; border-bottom-right-radius: 6px; }
.message-row.assistant .bubble-content { background: #f5f7fa; color: #333; border-bottom-left-radius: 6px; }
.chat-input-area { margin-top: 12px; border-top: 1px solid #eef2f6; padding-top: 12px; }
.input-box { margin-bottom: 8px; }
.controls { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.meta { color: #8b96a6; font-size: 13px; }
.actions { display: flex; gap: 8px; }
.btn { border: none; background: transparent; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn.clear { color: #606266; }
.btn.clear:hover { background: #f5f7fa; }
.btn.send { background: #409eff; color: #fff; display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; padding: 0; }
.btn.send:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(64,158,255,0.18); }
.btn.send.sending { opacity: 0.8; pointer-events: none; }
.send-icon { display: block; }

/* ==================== 记忆面板 ==================== */
.memory-panel { padding: 0 4px; }
.memory-empty { text-align: center; color: #999; padding: 32px 0; }
.memory-item { display: flex; align-items: flex-start; gap: 8px; padding: 12px; border-bottom: 1px solid #f0f0f0; }
.memory-tag { background: #ecf5ff; color: #409eff; font-size: 11px; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.memory-content { flex: 1; font-size: 13px; color: #333; line-height: 1.5; }
.memory-delete { border: none; background: transparent; color: #ccc; cursor: pointer; padding: 2px; flex-shrink: 0; }
.memory-delete:hover { color: #f56c6c; }

/* ==================== Loading ==================== */
.loading-indicator { display: flex; align-items: center; gap: 12px; justify-content: center; }
.three-body { --uib-size: 35px; --uib-speed: 0.8s; --uib-color: #5D3FD3; position: relative; display: inline-block; height: var(--uib-size); width: var(--uib-size); animation: spin78236 calc(var(--uib-speed) * 2.5) infinite linear; }
.three-body__dot { position: absolute; height: 100%; width: 30%; }
.three-body__dot:after { content: ''; position: absolute; height: 0%; width: 100%; padding-bottom: 100%; background-color: var(--uib-color); border-radius: 50%; }
.three-body__dot:nth-child(1) { bottom: 5%; left: 0; transform: rotate(60deg); transform-origin: 50% 85%; }
.three-body__dot:nth-child(1)::after { bottom: 0; left: 0; animation: wobble1 var(--uib-speed) infinite ease-in-out; animation-delay: calc(var(--uib-speed) * -0.3); }
.three-body__dot:nth-child(2) { bottom: 5%; right: 0; transform: rotate(-60deg); transform-origin: 50% 85%; }
.three-body__dot:nth-child(2)::after { bottom: 0; left: 0; animation: wobble1 var(--uib-speed) infinite calc(var(--uib-speed) * -0.15) ease-in-out; }
.three-body__dot:nth-child(3) { bottom: -5%; left: 0; transform: translateX(116.666%); }
.three-body__dot:nth-child(3)::after { top: 0; left: 0; animation: wobble2 var(--uib-speed) infinite ease-in-out; }
@keyframes spin78236 { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
@keyframes wobble1 { 0%, 100% { transform: translateY(0%) scale(1); opacity: 1; } 50% { transform: translateY(-66%) scale(0.65); opacity: 0.8; } }
@keyframes wobble2 { 0%, 100% { transform: translateY(0%) scale(1); opacity: 1; } 50% { transform: translateY(66%) scale(0.65); opacity: 0.8; } }

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .sidebar { position: fixed; left: 0; top: 60px; bottom: 0; z-index: 20; box-shadow: 2px 0 12px rgba(0,0,0,0.1); }
  .sidebar.collapsed { width: 0; }
  .bubble { max-width: 90%; }
}
</style>
