import { get, post, del } from '../utils/request.js'

export const listObservations = (metricType, pageNo = 1, pageSize = 20) =>
  get('/health/observations', {
    data: {
      ...(metricType && metricType !== 'all' ? { metric_type: metricType } : {}),
      page_no: pageNo,
      page_size: pageSize,
    },
  })

export const createObservation = (payload) =>
  post('/health/observations', payload, { idempotent: true })

export const deleteObservation = (id) => del(`/health/observations/${id}`)

export const getStats = (metricType) => get('/health/stats', { data: { metric_type: metricType } })
