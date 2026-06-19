import { post, get, del } from '../utils/request.js'
import config from '../utils/config.js'

export default {
  createConversation() {
    return post('/agent/conversations', {})
  },
  listConversations() {
    return get('/agent/conversations')
  },
  getMessages(cid) {
    return get(`/agent/conversations/${cid}/messages`)
  },
  deleteConversation(cid) {
    return del(`/agent/conversations/${cid}`)
  },
  sendMessage(cid, message) {
    return post(`/agent/conversations/${cid}/messages`, { message })
  },
  streamMessage(cid, message, { onDelta, onStatus, onEvent, onDone, onError } = {}) {
    // #ifndef H5
    return null
    // #endif

    // #ifdef H5
    if (typeof fetch !== 'function' || typeof TextDecoder === 'undefined') {
      return null
    }

    const controller = new AbortController()
    const token = uni.getStorageSync('token')
    const userId = uni.getStorageSync('userId')
    let doneCalled = false

    const finish = () => {
      if (doneCalled) return
      doneCalled = true
      onDone && onDone()
    }

    fetch(`${config.baseURL}/agent/conversations/${cid}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(userId ? { 'X-User-Id': String(userId) } : {})
      },
      body: JSON.stringify({ message }),
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text()
          onError && onError(text || `HTTP ${response.status}`)
          return
        }

        const reader = response.body && response.body.getReader ? response.body.getReader() : null
        if (!reader) {
          onError && onError('当前环境不支持流式读取')
          return
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''

          for (const block of blocks) {
            if (!block.trim()) continue
            let eventName = 'message'
            let data = ''

            for (const line of block.split('\n')) {
              if (line.startsWith('event:')) {
                eventName = line.substring(6).trim()
              } else if (line.startsWith('data:')) {
                data += line.substring(5)
              }
            }

            if (eventName === 'delta') {
              onDelta && onDelta(data)
            } else if (eventName === 'status') {
              onStatus && onStatus(data)
            } else if (
              eventName === 'tool_call' ||
              eventName === 'agent_step' ||
              eventName === 'intent' ||
              eventName === 'tool_start' ||
              eventName === 'tool_result' ||
              eventName === 'artifact' ||
              eventName === 'confirm_required'
            ) {
              onEvent && onEvent(eventName, data)
            } else if (eventName === 'done') {
              finish()
            } else if (eventName === 'error') {
              onError && onError(data)
            } else {
              onEvent && onEvent(eventName, data)
            }
          }
        }

        finish()
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          onError && onError(error.message || 'SSE 连接失败')
        }
      })

    return controller
    // #endif
  },
  async simpleChat(message) {
    const conversation = await this.createConversation()
    const cid = conversation && conversation.cid
    if (!cid) {
      throw new Error('AI 会话创建失败')
    }
    const reply = await this.sendMessage(cid, message)
    return reply && reply.content ? reply.content : reply
  },
  getMemories() {
    return get('/agent/memory')
  },
  deleteMemory(memId) {
    return del(`/agent/memory/${memId}`)
  }
}
