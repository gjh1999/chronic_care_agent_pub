import { get, post } from '../utils/request.js'

export const wechatLogin = (code) => post('/auth/wechat-login', { code })
export const getUserInfo = () => get('/auth/userinfo')
export const logout = () => post('/auth/logout', {})
