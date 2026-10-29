import { get, put } from '../utils/request.js'

export const getProfile = () => get('/me')
export const updateProfile = (patch) => put('/me', patch)
