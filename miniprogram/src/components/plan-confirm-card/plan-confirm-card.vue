<template>
  <view class="pcc">
    <view class="pcc-head">
      <text class="pcc-title">📋 {{ plan.summary || '健康计划草稿' }}</text>
      <text class="badge badge-orange">待确认</text>
      <text class="pcc-rev">版本 {{ revision }}</text>
    </view>

    <view class="pcc-items">
      <view v-for="(item, i) in plan.items" :key="i" class="pcc-item">
        <text class="pcc-index">{{ i + 1 }}</text>
        <view class="pcc-item-body">
          <text class="pcc-content">{{ mdToText(item.content) }}</text>
          <text v-if="scheduleText(item)" class="pcc-time">⏰ {{ scheduleText(item) }}</text>
        </view>
      </view>
    </view>

    <view class="pcc-actions">
      <button class="btn btn-danger pcc-btn" :disabled="disabled" @click="onReject">拒绝</button>
      <button class="btn btn-plain pcc-btn" :disabled="disabled" @click="showModify = true">修改</button>
      <button class="btn btn-primary pcc-btn" :disabled="disabled" @click="onConfirm">确认计划</button>
    </view>

    <!-- 修改弹窗 -->
    <view v-if="showModify">
      <view class="mask" @click="showModify = false"></view>
      <view class="sheet">
        <text class="sheet-title">修改计划</text>
        <text class="field-label">请输入你的修改意见(如:散步时间改到晚饭后)</text>
        <textarea
          class="field-textarea"
          v-model="modification"
          placeholder="我希望把散步时间改到晚饭后…"
          maxlength="500"
        />
        <view class="sheet-btns">
          <button class="btn btn-plain sheet-btn" @click="showModify = false">取消</button>
          <button class="btn btn-primary sheet-btn" @click="submitModify">提交修改</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { mdToText } from '../../utils/md.js'

const props = defineProps({
  plan: { type: Object, required: true },
  interruptId: { type: String, default: '' },
  revision: { type: Number, default: 1 },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'reject', 'modify'])

const showModify = ref(false)
const modification = ref('')

const scheduleText = (item) => {
  const s = item.schedule_rule || {}
  if (s.time && s.date) return `每天 ${s.time}`.replace('每天', `${s.date} `)
  if (s.time) return `每天 ${s.time}`
  if (s.date) return s.date
  return ''
}

const onConfirm = () => emit('confirm')
const onReject = () => emit('reject')
const submitModify = () => {
  emit('modify', modification.value.trim())
  modification.value = ''
  showModify.value = false
}
</script>

<style scoped>
.pcc {
  background: #ffffff;
  border: 1px solid #fbd38d;
  border-radius: 12px;
  padding: 14px;
  margin: 8px 0;
  box-shadow: 0 2px 6px rgba(221, 107, 32, 0.08);
}
.pcc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.pcc-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a202c;
  flex: 1;
}
.pcc-rev {
  font-size: 12px;
  color: #94a3b8;
}
.pcc-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pcc-item {
  display: flex;
  gap: 10px;
  background: #fffaf0;
  border-radius: 10px;
  padding: 10px 12px;
}
.pcc-index {
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  background: #dd6b20;
  color: #ffffff;
  border-radius: 50%;
  font-size: 13px;
  flex-shrink: 0;
  margin-top: 2px;
}
.pcc-item-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.pcc-content {
  font-size: 15px;
  color: #1a202c;
}
.pcc-time {
  font-size: 13px;
  color: #dd6b20;
}
.pcc-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.pcc-btn {
  flex: 1;
  height: 44px;
  line-height: 44px;
  font-size: 15px;
  padding: 0;
}
.sheet-title {
  font-size: 17px;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}
.sheet-btns {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.sheet-btn {
  flex: 1;
  height: 44px;
  line-height: 44px;
  font-size: 15px;
  padding: 0;
}
</style>
