import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ModelEntry } from '../types/model'
import { getModels as apiGetModels } from '../api/models'

export const useModelsStore = defineStore('models', () => {
  const models = ref<ModelEntry[]>([])
  const loading = ref(false)

  async function fetchModels() {
    loading.value = true
    try {
      models.value = await apiGetModels()
    } finally {
      loading.value = false
    }
  }

  return { models, loading, fetchModels }
})
