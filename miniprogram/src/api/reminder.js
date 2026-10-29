import { get, post } from '../utils/request.js'

export const listReminders = (status) => get('/reminders', { data: status && status !== 'all' ? { status } : {} })

export const createReminder = (payload) => post('/reminders', payload, { idempotent: true })

export const cancelReminder = (id) => post(`/reminders/${id}/cancel`, {})
