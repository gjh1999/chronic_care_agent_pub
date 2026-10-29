<template><view class="page"><view class="card"><picker :range="types" @change="change"><view>{{metric}}</view></picker><view>记录数：{{data.count || 0}}</view><view>平均值：{{data.average ?? '-'}}</view></view><view v-for="p in data.points" :key="p.observation_id" class="card">{{p.measured_at}} · {{p.value_num ?? `${p.systolic_value}/${p.diastolic_value}`}}</view></view></template>
<script setup>
import { ref, onMounted } from 'vue'; import { api } from '../../api'
const types=['blood_glucose','blood_pressure','weight']; const metric=ref(types[0]); const data=ref({points:[]})
async function load(){data.value=await api.stats(metric.value)} async function change(e){metric.value=types[e.detail.value];await load()} onMounted(load)
</script>
