const STREAM_STATE_KEY = 'campushub_ai_stream_states'

let runtimeStates = {}
const listeners = new Set()

function notifyListeners() {
  listeners.forEach(listener => {
    try {
      listener(runtimeStates)
    } catch (e) {
      // ignore listener errors so stream persistence keeps working
    }
  })
}

function getStorage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch (e) {
    return null
  }
}

export function readAgentStreamStates() {
  const storage = getStorage()
  if (storage) {
    try {
      const stored = storage.getItem(STREAM_STATE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed && typeof parsed === 'object') {
          runtimeStates = { ...runtimeStates, ...parsed }
        }
      }
    } catch (e) {
      // fall back to module memory
    }
  }
  return runtimeStates
}

export function writeAgentStreamStates(states) {
  runtimeStates = states || {}
  const storage = getStorage()
  if (storage) {
    try {
      storage.setItem(STREAM_STATE_KEY, JSON.stringify(runtimeStates))
    } catch (e) {
      // module memory remains available for same-page navigation
    }
  }
  notifyListeners()
}

export function clearAllAgentStreamStates() {
  runtimeStates = {}
  const storage = getStorage()
  if (storage) {
    try {
      storage.removeItem(STREAM_STATE_KEY)
    } catch (e) {
      // ignore
    }
  }
  notifyListeners()
}

export function subscribeAgentStreamStates(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
