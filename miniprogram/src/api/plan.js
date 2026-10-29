import { get, post } from '../utils/request.js'

export const listPlans = (status) => get('/plans', { data: status ? { status } : {} })
export const archivePlan = (planId) => post(`/plans/${planId}/archive`, {})
