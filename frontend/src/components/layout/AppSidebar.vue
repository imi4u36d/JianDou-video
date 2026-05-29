<template>
  <aside class="app-sidebar">
    <div class="sidebar-section">
      <h3>系统</h3>
      <SystemInfo />
    </div>
  </aside>
</template>

<script setup lang="ts">
import SystemInfo from '../common/SystemInfo.vue'
</script>

<style scoped>
.app-sidebar {
  width: 240px;
  min-height: calc(100vh - 56px);
  background: #16213e;
  color: #ccc;
  padding: 16px;
  font-size: 14px;
  border-right: 1px solid #2a2a3e;
}
.sidebar-section h3 {
  font-size: 12px;
  text-transform: uppercase;
  color: #888;
  margin: 0 0 8px 0;
}
</style>
