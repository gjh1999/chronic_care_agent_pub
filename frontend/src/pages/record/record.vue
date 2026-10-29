<template><view class="page"><view class="card"><picker :range="types" @change="type=types[$event.detail.value]"><view>指标：{{type}}</view></picker><input v-model="value" type="digit" placeholder="数值"/><button class="primary" @click="save">保存</button><button @click="uni.navigateTo({url:'/pages/stats/stats'})">查看趋势</button></view><view v-for="item in items" :key="item.observation_id" class="card">{{item.metric_type}}：{{item.value_num ?? `${item.systolic_value}/${item.diastolic_value}`}} {{item.unit}}</view></view></template>
<script setup>
import { ref, onMounted } from 'vue'; import { api } from '../../api'
const types=['blood_glucose','weight']; const type=ref(types[0]); const value=ref(''); const items=ref([])
async function load(){items.value=(await api.observations()).items}
async function save(){await api.createObservation({metric_type:type.value,value_num:Number(value.value),unit:type.value==='weight'?'kg':'mmol/L',measured_at:new Date().toISOString(),source:'manual'},`${Date.now()}`); value.value=''; await load()}
onMounted(load)
</script>
