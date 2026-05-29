import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SystemInfo } from '../types/system'
import client from '../api/client'

export const useSystemStore = defineStore('system', () => {
  const info = ref<SystemInfo | null>(null)
  const loading = ref(false)

  async function fetchSystemInfo() {
    loading.value = true
    try {
      const res = await client.get('/system/info')
      info.value = res.data
    } catch {
      // API not available yet
    } finally {
      loading.value = false
    }
  }

  return { info, loading, fetchSystemInfo }
})
