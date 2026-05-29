import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Task } from '../types/task'
import { createGeneration as apiCreateGeneration, type GenerateRequest } from '../api/generate'
import { getTasks as apiGetTasks } from '../api/tasks'

export const useGenerationStore = defineStore('generation', () => {
  const currentTask = ref<Task | null>(null)
  const tasks = ref<Task[]>([])
  const loading = ref(false)

  async function createGeneration(req: GenerateRequest) {
    loading.value = true
    try {
      const task = await apiCreateGeneration(req)
      currentTask.value = task
      return task
    } finally {
      loading.value = false
    }
  }

  async function fetchTasks() {
    tasks.value = await apiGetTasks()
  }

  return { currentTask, tasks, loading, createGeneration, fetchTasks }
})
