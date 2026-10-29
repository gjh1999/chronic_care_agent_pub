<template>
  <view class="chat-page">
    <!-- 顶部会话状态条 -->
    <view class="chat-status">
      <view class="status-dot" :class="status === 'waiting_confirmation' ? 'dot-orange' : 'dot-green'"></view>
      <text class="status-text">{{ status === 'waiting_confirmation' ? '等待你确认计划' : '会话进行中' }}</text>
      <text v-if="conversationId" class="status-id">会话 {{ conversationId.slice(0, 8) }}</text>
    </view>

    <!-- 消息列表 -->
    <scroll-view
      class="msg-list"
      scroll-y
      :scroll-into-view="scrollAnchor"
      :scroll-with-animation="true"
    >
      <view class="msg-wrap">
        <view v-if="!loaded && loading" class="empty">正在加载历史消息…</view>

        <view v-for="m in messages" :key="m.id" :id="'anchor-' + m.id">
          <!-- 用户消息:右 -->
          <view v-if="m.role === 'user'" class="row row-right">
            <view class="bubble bubble-user">{{ m.content }}</view>
          </view>

          <!-- 助手消息:左 -->
          <view v-else class="row row-left">
            <view class="avatar">助</view>
            <view class="bubble-col">
              <view class="bubble bubble-ai" :class="{ 'bubble-urgent': isUrgent(m.content) }">
                <text class="bubble-text">{{ mdToText(m.content) }}</text>
              </view>
              <!-- 计划确认卡片 -->
              <plan-confirm-card
                v-if="m.plan && m.status === 'waiting_confirmation' && !m.resolved"
                :plan="m.plan"
                :interrupt-id="m.interrupt_id"
                :revision="m.revision"
                :disabled="busy"
                @confirm="onConfirm(m)"
                @reject="onReject(m)"
                @modify="onModify(m, $event)"
              />
            </view>
          </view>
        </view>

        <!-- 思考中 -->
        <view v-if="thinking" id="anchor-thinking" class="row row-left">
          <view class="avatar">助</view>
          <view class="bubble bubble-ai">
            <view class="thinking-box">
              <view class="dots">
                <view class="dot"></view>
                <view class="dot"></view>
                <view class="dot"></view>
              </view>
              <text class="thinking-text">{{ thinkingText }}</text>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 快捷示例 -->
    <view class="quick">
      <text class="quick-item" @click="fillQuick('今天早餐后血糖 7.2')">测血糖</text>
      <text class="quick-item" @click="fillQuick('我刚测了血压')">测血压</text>
      <text class="quick-item" @click="fillQuick('帮我制定一个控糖计划')">生成计划</text>
      <text class="quick-item" @click="fillQuick('明早 7 点半提醒我测血糖')">设提醒</text>
    </view>

    <!-- 输入栏 -->
    <view class="input-bar">
      <input
        class="input"
        v-model="draft"
        placeholder="记录血糖/血压,或让我制定计划…"
        confirm-type="send"
        :disabled="busy"
        @confirm="send"
      />
      <button class="send-btn" :disabled="busy || !draft.trim()" @click="send">发送</button>
    </view>
    <view class="disclaimer">健康管理建议不替代医生诊断</view>
  </view>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { createConversation, getConversation, getMessages, sendMessage, resumeInterrupt } from '../../api/chat.js'
import { listPlans } from '../../api/plan.js'
import { errMsg, fmtDateTime } from '../../utils/request.js'
import { mdToText } from '../../utils/md.js'
// #ifdef H5
import { sendMessageStream } from '../../api/chat.js'
// #endif

const messages = ref([])
const draft = ref('')
const thinking = ref(false)
const thinkingText = ref('思考中,请稍候…')
const busy = ref(false)
// #ifdef H5
const streamMsg = ref(null)
// #endif
const status = ref('active')
const conversationId = ref('')
const scrollAnchor = ref('')
const loaded = ref(false)
const loading = ref(true)
let seq = 0

const isUrgent = (content) => (content || '').includes('🚨')

const scrollTo = (anchor) => {
  scrollAnchor.value = ''
  nextTick(() => {
    scrollAnchor.value = anchor
  })
}

const pushUser = (content) => {
  messages.value.push({ id: 'm' + ++seq, role: 'user', content })
}

const pushAssistant = (content, extra = {}) => {
  messages.value.push({ id: 'm' + ++seq, role: 'assistant', content, ...extra })
  scrollTo('anchor-m' + seq)
}

// 恢复历史:后端 structured_data 存了 status/interrupt_id/revision/plan_id,
// 计划项从草稿计划列表按 plan_id 关联
const loadHistory = async () => {
  const id = uni.getStorageSync('conversation_id') || ''
  if (!id) {
    loading.value = false
    loaded.value = true
    return
  }
  try {
    const conv = await getConversation(id)
    conversationId.value = id
    status.value = conv.status === 'waiting_confirmation' ? 'waiting_confirmation' : 'active'
    const msgs = await getMessages(id)

    let draftPlans = []
    if (conv.status === 'waiting_confirmation') {
      try {
        draftPlans = await listPlans('draft')
      } catch (e) {
        /* 草稿列表失败不阻断历史展示 */
      }
    }

    for (const m of msgs) {
      const extra = { status: 'completed' }
      const sd = m.structured_data || {}
      if (conv.status === 'waiting_confirmation' && sd.status === 'waiting_confirmation') {
        const plan = draftPlans.find((p) => p.plan_id === sd.plan_id)
        extra.status = 'waiting_confirmation'
        extra.resolved = false
        extra.interrupt_id = sd.interrupt_id
        extra.revision = sd.revision
        extra.plan = plan
          ? { summary: plan.summary || plan.title || '健康计划草稿', items: plan.items || [] }
          : null
      }
      messages.value.push({ id: 'm' + ++seq, role: m.role, content: m.content, ...extra })
    }
    scrollTo('anchor-m' + seq)
  } catch (e) {
    if (e && e.code === 40004) uni.removeStorageSync('conversation_id')
  } finally {
    loading.value = false
    loaded.value = true
  }
}

const fillQuick = (text) => {
  draft.value = text
}

const ensureConversation = async () => {
  if (conversationId.value) return
  const conv = await createConversation('')
  conversationId.value = conv.conversation_id
  uni.setStorageSync('conversation_id', conv.conversation_id)
}

// 将完成后的响应应用到界面:有草稿计划时挂确认卡片
const applyAssistantResponse = (res) => {
  if (res.status === 'waiting_confirmation') {
    status.value = 'waiting_confirmation'
    pushAssistant(res.final_response, {
      status: 'waiting_confirmation',
      resolved: false,
      interrupt_id: res.interrupt_id,
      revision: res.revision,
      plan: { summary: '健康计划草稿', items: res.plan || [] },
    })
  } else {
    status.value = 'active'
    pushAssistant(res.final_response, { status: 'completed' })
  }
}

// #ifdef H5
// 流式发送:状态进度更新"思考中"文案,首个 token 时创建流式气泡逐字增长,完成后落为正式回复
const sendStreaming = async (content) => {
  thinkingText.value = '已接收消息,开始处理…'
  const res = await sendMessageStream(conversationId.value, content, {
    onStatus: (text) => {
      thinkingText.value = text
    },
    onToken: (text) => {
      if (!streamMsg.value) {
        streamMsg.value = { id: 'm' + ++seq, role: 'assistant', content: '' }
        messages.value.push(streamMsg.value)
        thinking.value = false
        scrollTo('anchor-m' + seq)
      }
      streamMsg.value.content += text
    },
  })
  const msg = streamMsg.value
  streamMsg.value = null
  thinking.value = false
  if (msg) {
    msg.content = res.final_response || msg.content
    if (res.status === 'waiting_confirmation') {
      status.value = 'waiting_confirmation'
      msg.status = 'waiting_confirmation'
      msg.resolved = false
      msg.interrupt_id = res.interrupt_id
      msg.revision = res.revision
      msg.plan = { summary: '健康计划草稿', items: res.plan || [] }
    } else {
      status.value = 'active'
      msg.status = 'completed'
    }
    scrollTo('anchor-m' + seq)
  } else {
    applyAssistantResponse(res)
  }
}
// #endif

const send = async () => {
  const content = draft.value.trim()
  if (!content || busy.value) return
  draft.value = ''
  pushUser(content)
  scrollTo('anchor-m' + seq)
  thinking.value = true
  thinkingText.value = '思考中,请稍候…'
  busy.value = true
  try {
    await ensureConversation()
    // #ifdef H5
    await sendStreaming(content)
    // #endif
    // #ifndef H5
    const res = await sendMessage(conversationId.value, content)
    thinking.value = false
    applyAssistantResponse(res)
    // #endif
  } catch (e) {
    thinking.value = false
    // #ifdef H5
    streamMsg.value = null
    // #endif
    uni.showToast({ title: errMsg(e), icon: 'none' })
    pushAssistant('⚠️ 消息发送失败,请稍后重试。')
  } finally {
    busy.value = false
  }
}

const onConfirm = async (m) => {
  if (busy.value) return
  busy.value = true
  try {
    const res = await resumeInterrupt(conversationId.value, m.interrupt_id, 'confirm', m.revision)
    m.resolved = true
    m.status = 'completed'
    const reminders = res.reminders || []
    const skipped = res.skipped || []
    let text = '📋 计划已确认生效。'
    if (reminders.length) {
      text += `\n⏰ 已创建 ${reminders.length} 条提醒:\n` + reminders
        .map((r) => `· ${r.title}  ${fmtDateTime(r.next_run_at)}`)
        .join('\n')
    }
    if (skipped.length) text += `\n⚠️ ${skipped.length} 项未创建提醒(时间无法解析)。`
    pushAssistant(text)
    status.value = 'active'
    uni.showToast({ title: '计划已确认', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    busy.value = false
  }
}

const onReject = async (m) => {
  if (busy.value) return
  busy.value = true
  try {
    await resumeInterrupt(conversationId.value, m.interrupt_id, 'reject', m.revision)
    m.resolved = true
    m.status = 'completed'
    pushAssistant('已按你的要求拒绝该计划。如需调整,可以告诉我你的想法,我重新为你生成。')
    status.value = 'active'
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    busy.value = false
  }
}

const onModify = async (m, modification) => {
  if (busy.value || !modification) return
  busy.value = true
  try {
    const res = await resumeInterrupt(conversationId.value, m.interrupt_id, 'modify', m.revision, modification)
    m.resolved = true
    m.status = 'completed'
    if (res.status === 'waiting_confirmation') {
      status.value = 'waiting_confirmation'
      pushAssistant('已按你的修改意见重新生成计划草稿:')
      pushAssistant(res.final_response, {
        status: 'waiting_confirmation',
        resolved: false,
        interrupt_id: res.interrupt_id,
        revision: res.revision,
        plan: { summary: '健康计划草稿', items: res.plan || [] },
      })
    } else {
      status.value = 'active'
      pushAssistant(res.final_response || '计划已按修改意见处理。', { status: 'completed' })
    }
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    busy.value = false
  }
}

onMounted(loadHistory)
</script>

<style scoped>
.chat-page {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}
/* #ifdef H5 */
.chat-page {
  top: 44px;
  bottom: 50px;
}
/* #endif */

.chat-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot-green {
  background: #38a169;
}
.dot-orange {
  background: #dd6b20;
}
.status-text {
  font-size: 14px;
  color: #1a202c;
}
.status-id {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
}

.msg-list {
  flex: 1;
  overflow: hidden;
}
.msg-wrap {
  padding: 16px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.row {
  display: flex;
  align-items: flex-start;
}
.row-right {
  justify-content: flex-end;
}
.row-left {
  justify-content: flex-start;
}
.avatar {
  width: 36px;
  height: 36px;
  line-height: 36px;
  text-align: center;
  background: #2b6cb0;
  color: #ffffff;
  border-radius: 50%;
  font-size: 15px;
  flex-shrink: 0;
  margin-right: 8px;
}
.bubble-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 82%;
}
.bubble {
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 16px;
  line-height: 1.6;
  word-break: break-all;
}
.bubble-user {
  background: #2b6cb0;
  color: #ffffff;
  max-width: 82%;
  border-top-right-radius: 4px;
}
.bubble-ai {
  background: #ffffff;
  color: #1a202c;
  border-top-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
}
.bubble-urgent {
  background: #fff5f5;
  border: 1px solid #feb2b2;
}
.bubble-text {
  white-space: pre-wrap;
}

.thinking-box {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dots {
  display: flex;
  gap: 4px;
}
.dots .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2b6cb0;
  animation: bounce 1.2s infinite ease-in-out;
}
.dots .dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dots .dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}
.thinking-text {
  font-size: 14px;
  color: #64748b;
}

.quick {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: #f5f7fa;
  flex-wrap: wrap;
}
.quick-item {
  font-size: 13px;
  color: #2b6cb0;
  background: #ebf4fb;
  border-radius: 14px;
  padding: 4px 12px;
}

.input-bar {
  display: flex;
  gap: 10px;
  padding: 10px 16px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
}
.input {
  flex: 1;
  height: 44px;
  line-height: 44px;
  background: #f5f7fa;
  border-radius: 22px;
  padding: 0 16px;
  font-size: 16px;
}
.send-btn {
  width: 76px;
  height: 44px;
  line-height: 44px;
  background: #2b6cb0;
  color: #ffffff;
  border-radius: 22px;
  font-size: 16px;
  border: none;
  padding: 0;
}
.send-btn::after {
  border: none;
}
.send-btn[disabled] {
  background: #a0c4e8;
  color: #ffffff;
}
.disclaimer {
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  background: #ffffff;
  padding-bottom: 8px;
}
</style>
