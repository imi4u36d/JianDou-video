<template>
  <div class="system-info">
    <div v-if="store.info">
      <div class="info-row"><span>芯片:</span> {{ store.info.chip }}</div>
      <div class="info-row"><span>内存:</span> {{ store.info.ram_gb }} GB</div>
      <div class="info-row"><span>等级:</span> {{ store.info.tier }}</div>
    </div>
    <div v-else class="info-row muted">API 未连接</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSystemStore } from '../../stores/system'

const store = useSystemStore()

onMounted(() => {
  store.fetchSystemInfo()
})
</script>

<style scoped>
.system-info {
  font-size: 12px;
}
.info-row {
  margin-bottom: 4px;
}
.info-row span {
  color: #888;
}
.muted {
  color: #666;
}
</style>
