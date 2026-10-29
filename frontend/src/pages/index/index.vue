<template><view class="page"><view v-for="(item,i) in messages" :key="i" class="card"><view class="muted">{{ item.role }}</view><view>{{ item.content }}</view></view><view v-if="pending" class="card"><view>计划待确认</view><view v-for="(item,i) in pending.plan" :key="i">{{ item.task || item.content }}</view><button class="primary" @click="resume('confirm')">确认</button><button @click="resume('reject')">拒绝</button></view><textarea v-model="text" placeholder="例如：我今天空腹血糖 6.8，帮我记录"/><button class="primary" @click="send">发送</button></view></template>
<script setup>
import { ref } from 'vue'; import { api } from '../../api'
const text=ref(''); const messages=ref([]); const conversationId=ref(''); const pending=ref(null)
async function ensureConversation(){if(!conversationId.value) conversationId.value=(await api.createConversation('健康对话')).conversation_id}
async function send(){if(!text.value.trim())return; await ensureConversation(); const content=text.value; messages.value.push({role:'我',content}); text.value=''; const data=await api.sendMessage(conversationId.value,content); messages.value.push({role:'助手',content:data.final_response}); pending.value=data.status==='waiting_confirmation'?data:null}
async function resume(action){const data=await api.resume(conversationId.value,pending.value.interrupt_id,{action,revision:pending.value.revision}); messages.value.push({role:'系统',content:action==='confirm'?'计划已确认':'计划已拒绝'}); pending.value=null}
</script>
