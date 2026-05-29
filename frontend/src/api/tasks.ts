import client from './client'
import type { Task } from '../types/task'

export async function getTasks(params?: Record<string, string>): Promise<Task[]> {
  const res = await client.get('/tasks', { params })
  return res.data.tasks ?? []
}

export async function getTask(id: string): Promise<Task> {
  const res = await client.get(`/tasks/${id}`)
  return res.data
}

export async function deleteTask(id: string): Promise<void> {
  await client.delete(`/tasks/${id}`)
}

export async function retryTask(id: string): Promise<Task> {
  const res = await client.post(`/tasks/${id}/retry`)
  return res.data
}
