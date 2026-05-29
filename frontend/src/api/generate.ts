import client from './client'
import type { Task } from '../types/task'

export interface GenerateRequest {
  mode: string
  prompt: string
  negative_prompt?: string
  image_path?: string
  duration?: number
  width?: number
  height?: number
  fps?: number
  steps?: number
  cfg?: number
  seed?: number
  preset?: string
  upscale?: string
  upscale_factor?: number
  generate_audio?: boolean
}

export async function createGeneration(data: GenerateRequest): Promise<Task> {
  const res = await client.post('/generate', data)
  return res.data
}
