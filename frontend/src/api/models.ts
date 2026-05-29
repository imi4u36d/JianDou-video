import client from './client'
import type { ModelEntry, ModelDownloadProgress } from '../types/model'

export async function getModels(): Promise<ModelEntry[]> {
  const res = await client.get('/models')
  return res.data
}

export async function triggerDownload(repo: string, filename?: string): Promise<{ message: string; name: string; status: string }> {
  const res = await client.post('/models/download', { repo, filename })
  return res.data
}

export async function getDownloadProgress(name: string): Promise<ModelDownloadProgress> {
  const res = await client.get(`/models/download/${name}/progress`)
  return res.data
}

export async function getAllDownloadProgress(): Promise<{ downloads: any[] }> {
  const res = await client.get('/models/download/progress')
  return res.data
}
