import { request } from '../utils/request'

export const api = {
  login: code => request({ url: '/auth/wechat-login', method: 'POST', data: { code } }),
  logout: () => request({ url: '/auth/logout', method: 'POST' }),
  me: () => request({ url: '/me' }),
  updateMe: data => request({ url: '/me', method: 'PUT', data }),
  createConversation: title => request({ url: '/conversations', method: 'POST', data: { title } }),
  sendMessage: (id, content) => request({ url: `/conversations/${id}/messages`, method: 'POST', data: { content } }),
  resume: (id, interruptId, data) => request({ url: `/conversations/${id}/interrupts/${interruptId}/resume`, method: 'POST', data }),
  observations: metric => request({ url: `/health/observations${metric ? `?metric_type=${metric}` : ''}` }),
  createObservation: (data, key) => request({ url: '/health/observations', method: 'POST', data, headers: { 'Idempotency-Key': key } }),
  stats: metric => request({ url: `/health/stats?metric_type=${metric}` }),
  plans: () => request({ url: '/plans' }),
  reminders: () => request({ url: '/reminders' }),
  createReminder: data => request({ url: '/reminders', method: 'POST', data })
}
