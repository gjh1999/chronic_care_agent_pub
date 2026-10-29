import { get, post, BASE_URL, getToken } from '../utils/request.js'

// 对话链路真实 LLM 耗时 15s~190s,统一 300s 超时
const CHAT_TIMEOUT = 300000

export const createConversation = (title) => post('/conversations', { title })
export const getConversation = (id) => get(`/conversations/${id}`)
export const getMessages = (id) => get(`/conversations/${id}/messages`)
export const sendMessage = (id, content) =>
  post(`/conversations/${id}/messages`, { content }, { timeout: CHAT_TIMEOUT, idempotent: true })
export const resumeInterrupt = (id, interruptId, action, revision, modification) =>
  post(
    `/conversations/${id}/interrupts/${interruptId}/resume`,
    { action, revision, modification },
    { timeout: CHAT_TIMEOUT }
  )

// #ifdef H5
// SSE 流式发送:onStatus 推送阶段进度,onToken 逐字推送回复,最终 resolve done 事件的 response
export const sendMessageStream = (id, content, handlers = {}) =>
  new Promise((resolve, reject) => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT)
    const token = getToken()
    fetch(`${BASE_URL}/conversations/${id}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
        'Idempotency-Key': `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
      },
      body: JSON.stringify({ content }),
      signal: controller.signal,
    })
      .then((resp) => {
        if (!resp.ok || !resp.body) throw new Error(`请求失败(${resp.status})`)
        const reader = resp.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        const pump = () =>
          reader.read().then(({ done, value }) => {
            if (done) {
              clearTimeout(timeoutId)
              reject(new Error('流式连接意外中断'))
              return
            }
            buffer += decoder.decode(value, { stream: true })
            let idx
            while ((idx = buffer.indexOf('\n\n')) >= 0) {
              const raw = buffer.slice(0, idx)
              buffer = buffer.slice(idx + 2)
              const line = raw.split('\n').find((l) => l.startsWith('data: '))
              if (!line) continue
              let data
              try {
                data = JSON.parse(line.slice(6))
              } catch (e) {
                continue
              }
              if (data.type === 'status' && handlers.onStatus) handlers.onStatus(data.text)
              else if (data.type === 'token' && handlers.onToken) handlers.onToken(data.text)
              else if (data.type === 'done') {
                clearTimeout(timeoutId)
                resolve(data.response)
                return
              } else if (data.type === 'error') {
                clearTimeout(timeoutId)
                reject(new Error(data.message))
                return
              }
            }
            pump()
          })
          .catch((e) => {
            clearTimeout(timeoutId)
            reject(e)
          })
        pump()
      })
      .catch((e) => {
        clearTimeout(timeoutId)
        reject(e.name === 'AbortError' ? new Error('请求超时,请稍后重试') : e)
      })
  })
// #endif
