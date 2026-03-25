import api from '../utils/axios'

const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export default {
  createConversation() {
    return api.post('/agent/conversations')
  },

  listConversations() {
    return api.get('/agent/conversations')
  },

  getMessages(cid) {
    return api.get(`/agent/conversations/${cid}/messages`)
  },

  deleteConversation(cid) {
    return api.delete(`/agent/conversations/${cid}`)
  },

  // 非流式发送（降级用）
  sendMessage(cid, message) {
    return api.post(`/agent/conversations/${cid}/messages`, { message }, { timeout: 300000 })
  },

  /**
   * 流式发送消息 (SSE via fetch)
   * @returns {AbortController}
   */
  streamMessage(cid, message, { onDelta, onStatus, onDone, onError }) {
    const controller = new AbortController()
    const token = localStorage.getItem('token')
    const userId = localStorage.getItem('userId')

    fetch(`${baseUrl}/agent/conversations/${cid}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(userId ? { 'X-User-Id': userId } : {})
      },
      body: JSON.stringify({ message }),
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text()
          onError?.(text || `HTTP ${response.status}`)
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          // 按 \n\n 切分完整的 SSE 事件块
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() // 最后一段可能不完整，留在 buffer

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

            switch (eventName) {
              case 'delta':
                onDelta?.(data)
                break
              case 'status':
                onStatus?.(data)
                break
              case 'done':
                onDone?.()
                break
              case 'error':
                onError?.(data)
                break
            }
          }
        }

        // 流结束，如果没收到 done 事件也触发完成
        onDone?.()
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err.message || 'SSE 连接失败')
        }
      })

    return controller
  },

  getMemories() {
    return api.get('/agent/memory')
  },

  deleteMemory(memId) {
    return api.delete(`/agent/memory/${memId}`)
  }
}
